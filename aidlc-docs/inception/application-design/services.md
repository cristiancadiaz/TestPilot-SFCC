# Services — TestPilot SFCC (actualizado 2026-05-24)

> **Cambio mayor 2026-05-24:** S1 ahora recibe `SyntheticUserConfig` estructurado (no NL) y resuelve credenciales desde Secrets Manager. Se agregan S5–S8 para Environment Registry, EnvironmentResolver, LiveStatusTracker y Dashboard estático.

## S1: TestRunOrchestrationService

**Archivo**: `src/api/main.py` (endpoint POST /v1/run) + `src/api/services/run_orchestrator.py`
**Propósito**: Orquestar el flujo completo desde la request HTTP hasta la entrega del reporte
**Input**: `SyntheticUserConfig` estructurado vía Pydantic (D8 actualizada — ya NO NL)
**Output**: `ExecutionReport` (200) o error tipado según `application-design/error-taxonomy.md`

```
Request: SyntheticUserConfig {environment_id, products[], flows[], profiles[], capture_intermediate_screenshots=false}
    |
    v
[1] verify_api_key()                              -> 401 unauthorized si falla (H4.4)
    |
    v
[2] run_id = uuid4()                              (D9 — UUID4 server-side)
    |
    v
[3] env = EnvironmentResolver.resolve(            (★ NUEVO — S6)
        config.environment_id
    )                                              -> 404 environment_not_found
    |                                              -> 409 environment_inactive
    |                                              -> 502 secret_not_found
    v
[4] LiveStatusTracker.start(                      (★ NUEVO — S7)
        run_id, env.config.environment_id,
        started_at, config.profiles
    )
    |
    v
[5] async with asyncio.wait_for(timeout=1800):    (D10 actualizada — 30 min)
        async with Semaphore(MAX_CONCURRENT_PROFILES=3):
            results = await asyncio.gather(
                *[FlowRunner.run_profile(p, flow, config, env, run_id)
                  for p in profile_instances for flow in config.flows],
                return_exceptions=True,
            )
    |   produce: list[ProfileResult]
    |   actualiza LiveStatusTracker en cada transición
    |
    v
[6] ReportGenerator.generate_report(
        profile_results=results,
        baseline_store=baseline_store,
        config=config,
        run_id=run_id,
        env=env,                                  (★ baseline por ambiente)
        started_at=started_at,
    )
    |   primera línea: assert all(orders_created == 0) (H3.3 — invariante P1)
    |   produce: ExecutionReport
    |
    v
[7] baseline_store.save_run(RunRecord(...))       (por cada perfil; clave compuesta por ambiente)
    |
    v
[8] LiveStatusTracker.complete(run_id, traffic_light)
    |
    v
[9] return ExecutionReport (200) con header X-Run-Id: <run_id>
```

**Dependencias**:
- `EnvironmentResolver` (S6 — nuevo)
- `LiveStatusTracker` (S7 — nuevo)
- `FlowRunner` (C1-E)
- `ReportGenerator` (C3-A)
- `BaselineStore` (C2-A via C2-B)

**Manejo de errores** (ver `error-taxonomy.md`):
- Pydantic validation falla → 422 `validation_failed`
- `EnvironmentNotFoundError` → 404 `environment_not_found`
- `EnvironmentInactiveError` → 409 `environment_inactive`
- `SecretNotFoundError` → 502 `secret_not_found`
- `InvalidSecretPathError` → 422 `invalid_secret_path`
- `asyncio.TimeoutError` (watchdog) → 504 `run_timeout`
- `InvariantViolatedError` (orders_created != 0) → 500 `invariant_violated` + alerta crítica
- `InfrastructureError` capturado → 200 con `RunRecord.status="error"` + semáforo YELLOW
- Cualquier `Exception` no esperada → 500 `internal_error` (sin stack trace, H4.5 AC1)

**Decisiones aplicadas**: D1 (paralelización), D8 actualizada (input estructurado), D9 (run_id UUID4), D10 actualizada (timeout 1800s), D11 (auth fail-loud)

---

## S2: BaselineQueryService

**Archivo**: `src/api/routers/runs.py` (endpoints GET)
**Propósito**: Exponer el historial de runs para consulta por agentes CI/CD, dashboard y Tech Lead

```
GET /v1/runs/{run_id}
    [1] verify_api_key()
    [2] Pydantic valida UUID format
    [3] baseline_store.get_run(run_id)
    [4] 404 si None, 200 con ExecutionReport si encontrado

GET /v1/runs/latest
    [1] verify_api_key()
    [2] baseline_store.get_last_run()
    [3] calcular age_seconds = now - run.created_at
    [4] ttl_ok = age_seconds < 14400 (4h)
    [5] return ExecutionReportWithMeta

GET /v1/runs?filters                              (★ NUEVO RF-17)
    [1] verify_api_key()
    [2] Pydantic valida RunListQuery (env, traffic_light, flow, from_date, to_date, page, page_size)
    [3] default: últimos 7 días si no se especifican fechas (BR-U4-16)
    [4] baseline_store.list_runs(...)
    [5] return RunListResponse {items, page, page_size, total, has_more}
```

**Dependencias**: `BaselineStore` (C2-A) — método `list_runs` agregado en versión actual.

---

## S3: FlowExecutionService (local orchestrator)

**Archivo**: `src/executor/runner.py`
**Propósito**: Gestionar el ciclo de vida del browser + ejecución de las dos autenticaciones + flow funcional

```
run_profile(profile, flow_name, config, env: ResolvedEnvironment, run_id)
    |
    v
[0] Pre-condiciones (assertions):
    assert env.shopper.email.endswith("@testpilot.internal")  # BR-U1-03
    assert config.capture_intermediate_screenshots is False    # ADR-002
    |
    v
[1] async with async_playwright() as p:
[2]     browser = await p.chromium.launch(headless=True)
[3]     context = await browser.new_context(
              viewport={"width": profile.viewport_width, "height": profile.viewport_height},
              locale=profile.locale,
              user_agent=profile.user_agent,
              is_mobile=profile.is_mobile,
              http_credentials={                  (★ NUEVO — env_access auth)
                  "username": env.env_access.username,
                  "password": env.env_access.password,
              },
          )
[4]     page = await context.new_page()
[5]     env_step = await _execute_step(           (★ NUEVO — paso 1)
              page, "env_access_auth",
              lambda: page.goto(str(env.config.store_url)),
              config, run_id, profile.name, flow_name,
          )
        if env_step.status == "failed":
            raise InfrastructureError(...)
[6]     login_step = await shopper_login(         (★ NUEVO — paso 2)
              page, env.shopper, config, run_id, profile.name, flow_name,
          )
[7]     flow_fn = _get_flow_runner(flow_name)
[8]     flow_result = await flow_fn(page, config, env, run_id, profile.name)
[9]     flow_result.steps = [env_step, login_step] + flow_result.steps
[10]    assert flow_result.orders_created == 0
[11]    return ProfileResult(profile, flow_result, traffic_light=_initial_light(flow_result))
    finally:
        await browser.close()  # NFR-R2 — siempre cierra el browser
    
    except InfrastructureError as e:              # NFR-R1
        return ProfileResult con FlowResult(status="error") + TrafficLight=YELLOW
```

**Dependencias**: BrowserProfiles (C1-A), SFCCSelectors (C1-B incluyendo `LOGIN_*`), CheckoutFullFlow (C1-C), CheckoutCardDeclinedFlow (C1-D), `shopper_login` (nuevo en `src/executor/auth/`)

---

## S4: BaselineAnalysisService

**Archivo**: `src/baseline/baseline_manager.py`
**Propósito**: Funciones puras de análisis estadístico — diseñadas para ser testeadas con PBT

```
Al generar reporte (invocado por S1):
    runs = baseline_store.get_last_n_runs(
        environment_id=env.config.environment_id,  (★ clave compuesta por ambiente)
        profile=profile_name,
        flow=flow_name,
        n=10,
        status="success",
    )
    bootstrap = is_bootstrap_mode(runs)            # True si < 14 runs success
    p95 = calculate_p95(runs)                      # 0 si lista vacía
    traffic_light = compute_traffic_light(
        current_ms=current_run.duration_ms,
        p95_ms=p95,
        bootstrap=bootstrap,
    )
    return BaselineComparison(p95_ms, current_ms, bootstrap_mode, runs_count)
```

**Dependencias**: ninguna externa (funciones puras)
**PBT aplicable**: PBT-02, PBT-03, PBT-07, PBT-08, PBT-09 (todos bloqueantes)

---

## S5: EnvironmentRegistryService (★ NUEVO)

**Archivo**: `src/api/routers/environments.py` + `src/api/services/environment_registry.py`
**Propósito**: CRUD de `EnvironmentConfig` contra DynamoDB tabla `environments`. Sirve al dashboard P1 y a S6.

```
POST /v1/environments
    [1] verify_api_key()
    [2] Pydantic valida EnvironmentConfig
    [3] registry.get(environment_id) → 409 si ya existe
    [4] Verificar que ambos paths existen en Secrets Manager (BR-U4-07)
        → 422 invalid_secret_path si no
    [5] registry.create(config) → DynamoDB put_item
    [6] return 201 con EnvironmentConfig

GET /v1/environments
    [1] verify_api_key()
    [2] registry.list(only_active=query_param)
    [3] return 200 con list[EnvironmentConfig]

GET /v1/environments/{id}
    [1] verify_api_key()
    [2] registry.get(id) → 404 si no existe
    [3] return 200 con EnvironmentConfig

PUT /v1/environments/{id}
    [1] verify_api_key()
    [2] Validar updates (no permitir cambio de environment_id — 400)
    [3] registry.update(id, updates)
    [4] registry.invalidate(id) — clear caches del resolver
    [5] return 200 con EnvironmentConfig actualizado

DELETE /v1/environments/{id}
    [1] verify_api_key()
    [2] registry.deactivate(id) — soft delete (active=false)
    [3] return 204 No Content
```

**Dependencias**: DynamoDB tabla `environments` (creada por IaC en Operations), `SecretsManagerClient` (S6) para validación de paths en CREATE.

**Caché**: TTL 60s en memoria por `environment_id` (NFR-U4-P1).

---

## S6: EnvironmentResolverService (★ NUEVO)

**Archivo**: `src/api/services/environment_resolver.py`
**Propósito**: Resolver `environment_id` → `ResolvedEnvironment` (config + credenciales). Caché TTL 5 min.

```
resolve(environment_id) → ResolvedEnvironment
    [1] cache.get(environment_id) → si hit, return
    [2] config = registry.get(environment_id)
        → raise EnvironmentNotFoundError si None
        → raise EnvironmentInactiveError si not config.active
    [3] env_access_dict = secrets.get_json(config.env_access_secret_path)
        → raise SecretNotFoundError si falla
    [4] shopper_dict = secrets.get_json(config.shopper_secret_path)
        → raise SecretNotFoundError si falla
    [5] env = ResolvedEnvironment(
            config=config,
            env_access=EnvironmentAccessCredentials(**env_access_dict),
            shopper=ShopperCredentials(**shopper_dict),
        )
        → raise InvalidSecretPathError si Pydantic falla
    [6] cache.set(environment_id, env, ttl=300)
    [7] return env
```

**Dependencias**: `EnvironmentRegistry` (S5), `SecretsManagerClient`.

**Por qué TTL 5 min:** permite que rotación manual de secrets se propague rápido (max 5 min de latencia) sin sobrecargar Secrets Manager.

---

## S7: LiveStatusTrackerService (★ NUEVO)

**Archivo**: `src/api/services/live_status_tracker.py`
**Propósito**: Mantener estado de runs en curso para servir `GET /v1/runs/{id}/status` consumido por el dashboard P3 vía polling.

```
start(run_id, env_id, started_at, profile_ids)
    [1] lock.acquire()
    [2] si len(_runs) >= MAX_RUNS (100): popitem(oldest)
    [3] _runs[run_id] = RunStatus(state=RUNNING, profiles=[...pending...])

update_profile(run_id, profile_id, *, state, current_step=None, steps_completed=None)
    [1] lock.acquire()
    [2] _runs[run_id].profiles[i].state = state (etc.)

complete(run_id, traffic_light)
    [1] lock.acquire()
    [2] _runs[run_id].state = COMPLETED

fail(run_id, error)
    [1] lock.acquire()
    [2] _runs[run_id].state = FAILED

get(run_id) → RunStatus | None
    [1] lock.acquire()
    [2] return _runs.get(run_id)
```

**Dependencias**: ninguna externa. Estado in-memory con ring buffer FIFO (max 100 runs).

**Limitación MVP:** estado se pierde al restart de la task ECS. Si un dashboard estaba mirando un run y la task muere, recibe 404 — debe consultar `/v1/runs/{id}` directamente. Post-MVP: persistir en DynamoDB con TTL.

---

## S8: DashboardStaticService (★ NUEVO)

**Archivo**: `src/api/main.py` (mount de StaticFiles)
**Propósito**: Servir los archivos estáticos del dashboard MD0 desde `src/dashboard/dist/`.

```
GET /                              → src/dashboard/dist/index.html
GET /assets/*                      → src/dashboard/dist/assets/*
GET /{spa-route}                   → fallback a index.html (SPA routing)
```

**Configuración:**
```python
from fastapi.staticfiles import StaticFiles
from pathlib import Path

DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard" / "dist"
if DASHBOARD_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")
```

**Si `dist/` no existe** (ej. tests sin build), el mount se omite y la API sigue funcional (BR-U4-22).

**Security headers**: aplicados por `SecurityHeadersMiddleware` (CSP, X-Frame-Options, etc.) — ver `construction/u4/nfr-design/nfr-design.md` Patrón 7 y BR-U4-23.

**Orden de routing:** `/v1/*` y `/health` se registran primero (prioridad). El mount `StaticFiles` al final captura el resto.

---

## Resumen de servicios

| Servicio | Estado | Responsabilidad |
|---|---|---|
| S1 TestRunOrchestrationService | Actualizado | Orquestar POST /v1/run con resolución de ambiente |
| S2 BaselineQueryService | Actualizado | GET endpoints incluyendo listado paginado |
| S3 FlowExecutionService | Actualizado | Browser + dos autenticaciones + flow |
| S4 BaselineAnalysisService | Actualizado | Funciones puras con clave por ambiente |
| S5 EnvironmentRegistryService | ★ Nuevo | CRUD environments en DynamoDB |
| S6 EnvironmentResolverService | ★ Nuevo | environment_id → ResolvedEnvironment con caché |
| S7 LiveStatusTrackerService | ★ Nuevo | Estado vivo para dashboard polling |
| S8 DashboardStaticService | ★ Nuevo | Servir archivos estáticos de MD0 |
