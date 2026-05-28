# Business Logic Model — U4 API Endpoints (actualizado 2026-05-24)

## Propósito desde la perspectiva del producto

U4 es la **superficie pública del producto** + el **backend del dashboard MD0**. Todo lo construido en U1–U3 solo es útil si Carolina (o el dashboard, o un agente CI/CD) puede invocarlo vía HTTP.

**Cambios mayores vs versión anterior:**
1. **Environment Registry CRUD** — gestión de ambientes (sandbox/development/staging) persistidos en DynamoDB.
2. **Resolución de credenciales** desde Secrets Manager — convierte `environment_id` → `ResolvedEnvironment`.
3. **Endpoints en tiempo real** — `GET /v1/runs/{id}/status` para que el dashboard P3 haga polling.
4. **Endpoint de historial filtrable** — `GET /v1/runs?filters` para P5.
5. **Endpoint de health** — para healthcheck de ECS y CloudWatch.
6. **Servir estáticos** del dashboard MD0 (mount al final).

**Outcomes de negocio:**
- **API pública versionada** (`/v1/`) consumible por dashboard, agentes CI/CD, scripts.
- **Resolución segura de credenciales** — `environment_id` en cliente → credenciales reales en backend, sin viajar.
- **Visibilidad del progreso** — el dashboard puede mostrar runs vivos en P3.
- **Auditabilidad histórica** — historial paginado con filtros para compliance.

---

## Endpoints (expandidos)

### Endpoints públicos `/v1/`

| Método | Path | Auth | Propósito |
|---|---|---|---|
| GET | `/health` | NO | Healthcheck (ECS readiness/liveness) |
| GET | `/v1/environments` | ✅ | Listar ambientes registrados |
| GET | `/v1/environments/{id}` | ✅ | Detalle de un ambiente |
| POST | `/v1/environments` | ✅ | Crear nuevo ambiente |
| PUT | `/v1/environments/{id}` | ✅ | Actualizar ambiente (no `environment_id`) |
| DELETE | `/v1/environments/{id}` | ✅ | Desactivar (soft delete — `active=false`) |
| POST | `/v1/run` | ✅ | Lanzar run sincrónicamente — retorna ExecutionReport |
| GET | `/v1/runs/{id}` | ✅ | Detalle de un run terminado |
| GET | `/v1/runs/{id}/status` | ✅ | Estado vivo de un run (para polling P3) |
| GET | `/v1/runs/latest` | ✅ | Run más reciente con `age_seconds` y `ttl_ok` |
| GET | `/v1/runs` | ✅ | Historial filtrable + paginado |
| GET | `/v1/runs/{id}/screenshots/{path}` | ✅ | Servir screenshot desde S3 (proxy presigned) |

### Estáticos del dashboard
| Método | Path | Propósito |
|---|---|---|
| GET | `/` | `index.html` del dashboard MD0 |
| GET | `/assets/*` | Bundles JS/CSS de Vite |
| GET | `/{spa-route}` | Catch-all → `index.html` para SPA routing |

**Orden de routing:** `/health` y `/v1/*` se montan primero (prioridad). El `StaticFiles` mount al final captura el resto.

---

## Componentes del módulo U4

```
src/api/
├── __init__.py
├── main.py                    # FastAPI app + router includes
├── auth.py                    # verify_api_key dependency
├── middleware.py              # SecurityHeadersMiddleware (CSP, etc.)
├── exceptions.py              # exception handlers (404, 422, 500, etc.)
├── routers/
│   ├── __init__.py
│   ├── health.py              # GET /health
│   ├── environments.py        # CRUD environments
│   ├── runs.py                # POST /run + GET runs
│   └── screenshots.py         # GET /runs/{id}/screenshots/{path}
├── services/
│   ├── __init__.py
│   ├── environment_registry.py    # CRUD DynamoDB + cache
│   ├── environment_resolver.py    # environment_id → ResolvedEnvironment
│   ├── secrets_manager.py         # boto3 wrapper para Secrets Manager
│   ├── run_orchestrator.py        # POST /run business logic
│   └── live_status_tracker.py     # estado de runs en curso (in-memory ring)
└── deps.py                    # FastAPI Depends helpers
```

---

## Servicios clave

### EnvironmentRegistry
**Responsabilidad:** CRUD de `EnvironmentConfig` contra DynamoDB tabla `environments`.

```python
class EnvironmentRegistry:
    def __init__(self, table_name: str) -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)
    
    def list(self, only_active: bool = False) -> list[EnvironmentConfig]: ...
    def get(self, environment_id: str) -> EnvironmentConfig | None: ...
    def create(self, config: EnvironmentConfig) -> EnvironmentConfig: ...
    def update(self, environment_id: str, updates: dict) -> EnvironmentConfig: ...
    def deactivate(self, environment_id: str) -> None: ...  # set active=false
```

**Caché:** lookup por `environment_id` con TTL 60 s en memoria. Reduce calls a DynamoDB durante polling de runs.

### EnvironmentResolver
**Responsabilidad:** convertir `environment_id` → `ResolvedEnvironment` resolviendo credenciales desde Secrets Manager.

```python
class EnvironmentResolver:
    def __init__(
        self,
        registry: EnvironmentRegistry,
        secrets: SecretsManagerClient,
    ) -> None:
        self._registry = registry
        self._secrets = secrets
    
    def resolve(self, environment_id: str) -> ResolvedEnvironment:
        config = self._registry.get(environment_id)
        if not config:
            raise EnvironmentNotFoundError(environment_id)
        if not config.active:
            raise EnvironmentInactiveError(environment_id)
        
        env_access = self._secrets.get_json(config.env_access_secret_path)
        shopper = self._secrets.get_json(config.shopper_secret_path)
        
        return ResolvedEnvironment(
            config=config,
            env_access=EnvironmentAccessCredentials(**env_access),
            shopper=ShopperCredentials(**shopper),
        )
```

**Caché de credenciales:** TTL 5 min en memoria — reduce calls a Secrets Manager (que tiene rate limits). El TTL corto permite rotación sin restart.

### SecretsManagerClient
Wrapper minimalista boto3:

```python
class SecretsManagerClient:
    def __init__(self) -> None:
        self._client = boto3.client("secretsmanager")
    
    def get_json(self, secret_path: str) -> dict:
        response = self._client.get_secret_value(SecretId=secret_path)
        return json.loads(response["SecretString"])
```

### RunOrchestrator
**Responsabilidad:** lógica de `POST /v1/run`. Orquesta executor + baseline + reporter.

```python
class RunOrchestrator:
    def __init__(
        self,
        resolver: EnvironmentResolver,
        baseline_store: BaselineStore,
        live_tracker: LiveStatusTracker,
        max_concurrent_profiles: int = 3,
    ) -> None: ...
    
    async def run(self, config: SyntheticUserConfig) -> ExecutionReport:
        # 1. Resolver ambiente
        env = self._resolver.resolve(config.environment_id)
        
        # 2. Generar run_id
        run_id = str(uuid4())
        started_at = datetime.now(timezone.utc)
        
        # 3. Registrar run vivo
        self._live_tracker.start(run_id, env.config.environment_id, started_at, config.profiles)
        
        try:
            # 4. Resolver profiles a instancias BrowserProfile
            profile_instances = [_resolve_profile(p) for p in config.profiles]
            
            # 5. Ejecutar perfiles en paralelo (cap MAX_CONCURRENT_PROFILES)
            sem = asyncio.Semaphore(self._max_concurrent_profiles)
            
            async def _bounded_run(profile, flow_name):
                async with sem:
                    self._live_tracker.update_profile(run_id, profile.name, state="running")
                    result = await run_profile(profile, flow_name, config, env, run_id)
                    self._live_tracker.update_profile(run_id, profile.name, state=result.flow_result.status)
                    return result
            
            tasks = [
                _bounded_run(profile, flow)
                for profile in profile_instances
                for flow in config.flows
            ]
            profile_results = await asyncio.gather(*tasks)
            
            # 6. Generar reporte
            report = generate_report(
                profile_results=profile_results,
                baseline_store=self._baseline_store,
                config=config,
                run_id=run_id,
                env=env,
                started_at=started_at,
            )
            
            # 7. Persistir reporte
            self._save_report(report)
            
            # 8. Marcar run vivo como completado
            self._live_tracker.complete(run_id, report.traffic_light)
            
            return report
        
        except Exception as exc:
            self._live_tracker.fail(run_id, str(exc))
            raise
```

### LiveStatusTracker
**Responsabilidad:** mantener estado de runs en curso para servir `GET /v1/runs/{id}/status`.

```python
class LiveStatusTracker:
    """
    Estado in-memory (ring buffer de los últimos 100 runs).
    Suficiente para MVP — un run completo dura ~12 min, dashboard pollea cada 3s,
    100 runs es ~20 horas de historial vivo.
    """
    def __init__(self, max_runs: int = 100) -> None:
        self._runs: OrderedDict[str, RunStatus] = OrderedDict()
        self._max = max_runs
    
    def start(self, run_id, env_id, started_at, profile_ids): ...
    def update_profile(self, run_id, profile_id, *, state, current_step=None, steps_completed=None): ...
    def complete(self, run_id, traffic_light): ...
    def fail(self, run_id, error): ...
    def get(self, run_id) -> RunStatus | None: ...
```

---

## Flujos de endpoints

### POST /v1/run

```
1. verify_api_key (dependency)
2. Pydantic valida SyntheticUserConfig (422 si falla)
3. orchestrator.run(config) → ExecutionReport
   - resuelve ambiente
   - registra en live_tracker
   - ejecuta perfiles en paralelo
   - genera reporte
   - persiste
4. Retornar 200 con to_json_dict(report)
```

**Errores:**
- 401 `unauthorized`
- 404 `environment_not_found`
- 409 `environment_inactive`
- 422 `validation_failed`
- 502 `secret_not_found` (Secrets Manager no responde o path inválido)
- 504 `run_timeout` (run excede watchdog de 30 min)
- 500 `invariant_violated` (orders_created != 0 — incidente crítico)
- 500 `internal_error` (catch-all sin stack trace)

### GET /v1/runs/{run_id}

```
1. verify_api_key
2. Validar UUID format
3. baseline_store.get_run(run_id) → 404 si no existe
4. Retornar 200 con to_json_dict(report)
```

### GET /v1/runs/{run_id}/status

```
1. verify_api_key
2. live_tracker.get(run_id) → 404 si no existe
3. Retornar 200 con RunStatus (model_dump)
```

**Comportamiento:**
- Si run aún en curso: `state="running"`, `profiles` con estado vivo.
- Si run terminado: `state="completed"` o `"failed"` + último snapshot.
- Si run no existe en tracker pero sí en baseline_store: redirige (302) a `/v1/runs/{id}`.

### GET /v1/runs (historial)

```
1. verify_api_key
2. Parsear query params:
   - environment_id (opcional)
   - traffic_light (opcional)
   - from_date, to_date (opcional, default últimos 7 días)
   - flow (opcional)
   - page (default 1), page_size (default 25, max 100)
3. baseline_store.list_runs(...)
4. Retornar 200 con {items: [...], page, page_size, total, has_more}
```

### POST /v1/environments

```
1. verify_api_key
2. Pydantic valida EnvironmentConfig (422 si falla)
3. registry.get(environment_id) → 409 si ya existe
4. registry.create(config)
5. Retornar 201 con EnvironmentConfig creado
```

### PUT /v1/environments/{id}

```
1. verify_api_key
2. Pydantic valida updates (subset de campos editables)
3. registry.get(environment_id) → 404 si no existe
4. Rechazar update de environment_id (400)
5. registry.update(environment_id, updates)
6. Retornar 200 con EnvironmentConfig actualizado
```

### GET /v1/runs/{id}/screenshots/{path}

```
1. verify_api_key
2. Validar formato de path (regex: {profile}/{flow}/{step}-{ok|fail}.png)
3. Construir S3 key: {run_id}/{path}
4. Generar presigned URL (TTL 5 min) o proxy bytes
5. Retornar 200 con image/png
```

**Decisión:** MVP usa **proxy directo** (FastAPI lee de S3 y sirve). Post-MVP: presigned URL con redirect 302.

---

## Estrategia de persistencia

**MVP (sprint 0-2):**
- `EnvironmentRegistry`: DynamoDB `environments` (necesario desde día 1 — el dashboard P1 lo gestiona).
- `BaselineStore`: `InMemoryBaselineStore` (se pierde al restart — aceptable en MVP).
- `LiveStatusTracker`: in-memory ring buffer.

**Sprint 3+:**
- `BaselineStore`: migrar a `DynamoDBBaselineStore` con tabla `runs`.
- `LiveStatusTracker`: agregar persistencia a DynamoDB con TTL.

---

## Healthcheck

```
GET /health (sin auth)

200 OK:
  {
    "status": "healthy",
    "checks": {
      "dynamodb_environments": "ok",
      "secrets_manager": "ok",
      "live_tracker": "ok"
    },
    "version": "1.0.0",
    "git_sha": "abc123def"
  }

503 Service Unavailable si algún check falla.
```

Verifica:
- `dynamodb.describe_table("environments")` < 500 ms
- `secrets_manager.list_secrets(MaxResults=1)` < 500 ms
- `live_tracker._runs` accesible

---

## Watchdog de runs

`POST /v1/run` es sincrónico — el caller espera la response (12 min típico). Configuración:
- `RUN_TIMEOUT_MS = 30 * 60 * 1000` (30 min)
- `asyncio.wait_for(orchestrator.run(config), timeout=RUN_TIMEOUT_MS / 1000)`
- Si vence: 504 `run_timeout`, run marcado como failed en live_tracker

Cliente sugerido: timeout HTTP 35 min para dar margen al watchdog.

---

## Criterio de completitud (Definition of Done)

- [ ] Todos los endpoints retornan códigos HTTP correctos según error-taxonomy.
- [ ] Ningún endpoint retorna stack traces.
- [ ] Auth en todos los endpoints excepto `/health`.
- [ ] CORS configurado correctamente (sin CORS — same-origin con dashboard).
- [ ] Security headers (CSP, X-Frame-Options, etc.) en responses de estáticos.
- [ ] CRUD de environments completo y testeado.
- [ ] Resolución de credenciales con manejo de error en Secrets Manager.
- [ ] LiveStatusTracker se actualiza durante runs en paralelo (test con mock).
- [ ] Historial paginado funciona con filtros.
- [ ] `/health` retorna 503 si dependencias caen.
- [ ] H4.1–H4.5 + H5.1–H5.4 AC satisfechos.
