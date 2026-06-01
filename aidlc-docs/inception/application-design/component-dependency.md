# Component Dependencies — TestPilot SFCC (actualizado 2026-05-24)

> **Cambio mayor 2026-05-24:** se agrega C-D0 DashboardApp y se expanden los componentes de U4 con 5 services (C4-B a C4-F). Se documentan dependencias contra DynamoDB, S3 y Secrets Manager (resueltas en runtime, no en compile).

## Dependency Matrix

| Componente | Depende de | Tipo | Razón |
|------------|-----------|------|-------|
| **C-D0 DashboardApp (MD0)** | C0-A SharedModels (proyección TS) | contract | Interfaces TypeScript derivan de modelos Pydantic |
| **C-D0 DashboardApp (MD0)** | C4-A APIRouter (REST API) | runtime | Consume `/v1/*` endpoints — único consumidor del API junto a agentes CI/CD externos |
| C0-C TranslatorAgent | C0-A SharedModels | compile | `SyntheticUserConfig` (importa en lugar de definir) — funcionalidad opcional, ya no es entrada principal |
| C1-A BrowserProfiles | C0-A SharedModels | compile | `BrowserProfile` |
| C1-B SFCCSelectors | — | — | Sin dependencias (catálogo de strings) — incluye `LOGIN_*` |
| **C1-Auth shopper_login** | C0-A SharedModels | compile | `ShopperCredentials`, `StepResult`, `SyntheticUserConfig` |
| **C1-Auth shopper_login** | C1-B SFCCSelectors | compile | `LOGIN_EMAIL_INPUT`, `LOGIN_PASSWORD_INPUT`, etc. |
| C1-C CheckoutFullFlow | C0-A SharedModels | compile | `StepResult`, `FlowResult`, `SyntheticUserConfig`, `ResolvedEnvironment` |
| C1-C CheckoutFullFlow | C1-B SFCCSelectors | compile | Selectores para pasos del flow |
| C1-D CheckoutCardDeclinedFlow | C0-A SharedModels | compile | Misma razón que C1-C |
| C1-D CheckoutCardDeclinedFlow | C1-B SFCCSelectors | compile | Selectores incluyendo `DECLINE_*` |
| C1-E FlowRunner | C0-A SharedModels | compile | `BrowserProfile`, `ProfileResult`, `ResolvedEnvironment` |
| C1-E FlowRunner | C1-A BrowserProfiles | compile | Instancias de `BrowserProfile` |
| C1-E FlowRunner | C1-Auth shopper_login | runtime | Ejecuta paso de login |
| C1-E FlowRunner | C1-C CheckoutFullFlow | runtime | Delega ejecución del flow |
| C1-E FlowRunner | C1-D CheckoutCardDeclinedFlow | runtime | Delega ejecución del flow |
| C2-B InMemoryBaselineStore | C0-A SharedModels | compile | `RunRecord` (con `environment_id` en clave compuesta) |
| C2-C BaselineCalculator | C0-A SharedModels | compile | `RunRecord`, `TrafficLight` |
| C3-A ReportGenerator | C0-A SharedModels | compile | `ExecutionReport`, `ProfileResult`, `TrafficLight`, `ResolvedEnvironment` |
| C3-A ReportGenerator | C2-A BaselineStore (Protocol) | compile | Consulta baseline vía interfaz pasando `environment_id` |
| C3-A ReportGenerator | C2-C BaselineCalculator | compile | `compute_traffic_light`, `is_bootstrap_mode` |
| C4-A APIRouter | C0-A SharedModels | compile | Todos los modelos compartidos |
| C4-A APIRouter | C4-E RunOrchestrator | runtime | Lanza orquestación de POST /v1/run |
| C4-A APIRouter | C4-B EnvironmentRegistry | runtime | CRUD endpoints |
| C4-A APIRouter | C4-F LiveStatusTracker | runtime | GET /status |
| C4-A APIRouter | C2-A BaselineStore (Protocol) | runtime | GET /runs/{id} y /runs/latest y /runs?filters |
| **C4-B EnvironmentRegistry** | C0-A SharedModels | compile | `EnvironmentConfig` |
| **C4-B EnvironmentRegistry** | DynamoDB tabla `environments` | runtime | Persistencia (resuelto vía boto3) |
| **C4-C EnvironmentResolver** | C4-B EnvironmentRegistry | compile | Lookup de `EnvironmentConfig` |
| **C4-C EnvironmentResolver** | C4-D SecretsManagerClient | compile | Resolver credenciales |
| **C4-C EnvironmentResolver** | C0-A SharedModels | compile | `ResolvedEnvironment`, `EnvironmentAccessCredentials`, `ShopperCredentials` |
| **C4-D SecretsManagerClient** | AWS Secrets Manager | runtime | Recuperar secrets (vía boto3) |
| **C4-E RunOrchestrator** | C4-C EnvironmentResolver | compile | `resolve(environment_id)` |
| **C4-E RunOrchestrator** | C1-E FlowRunner | runtime | `run_profile(...)` paralelizado |
| **C4-E RunOrchestrator** | C3-A ReportGenerator | runtime | `generate_report(...)` |
| **C4-E RunOrchestrator** | C2-A BaselineStore | runtime | `save_run(...)` |
| **C4-E RunOrchestrator** | C4-F LiveStatusTracker | runtime | Actualiza estado vivo durante ejecución |
| **C4-F LiveStatusTracker** | C0-A SharedModels | compile | `RunStatus`, `ProfileLiveStatus`, `RunState` |

## Data Flow Diagram

```
                                           ┌─────────────────┐
                                           │  Dashboard MD0  │ (C-D0)
                                           │ (browser SPA)   │
                                           └────────┬────────┘
                                                    │
                                                    │ HTTPS GET/POST /v1/* + X-API-Key
                                                    │ (polling 3s para /status)
                                                    │
                                                    ▼
[Agentes CI/CD externos] ─────────────────► [C4-A APIRouter]
                                              verify_api_key()
                                              │
              ┌───────────────────────────────┼─────────────────────┐
              │                               │                     │
              ▼                               ▼                     ▼
   [C4-B EnvironmentRegistry]    [C4-E RunOrchestrator]   [C2-A BaselineStore]
              │                       │                            (lectura para
              │                       ▼                             /runs, /runs/latest,
              ▼                  [C4-C EnvironmentResolver]         /runs/{id})
       DynamoDB                       │
       `environments`                 │ resolve(env_id)
                                      │
                       ┌──────────────┼──────────────┐
                       ▼              ▼              ▼
            [C4-B Registry]  [C4-D SecretsClient]   ┌─────────────┐
                       │              │              │ AWS Secrets │
                       │              └─────────────►│  Manager    │
                       ▼                             │ env_access  │
                  (cached config)                    │  + shopper  │
                                                     └─────────────┘
                                                            │
                                                            ▼
                                            [C4-E RunOrchestrator]
                                            asyncio.gather con sem=3
                                                            │
                                ┌───────────────────────────┼──────────────┐
                                ▼                           ▼              ▼
                       [C4-F LiveStatusTracker]  [C1-E FlowRunner]  [C1-E FlowRunner]
                       (actualiza estado vivo)    (perfil 1)         (perfil 2)
                                                       │                  │
                                                       ▼                  ▼
                                              [browser Chromium]   [browser Chromium]
                                              http_credentials      http_credentials
                                              env_access            env_access
                                                       │                  │
                                                       ▼                  ▼
                                              Storefront SFCC      Storefront SFCC
                                              (env_access_auth     (env_access_auth
                                              + shopper_login +    + shopper_login +
                                              flow funcional)      flow funcional)
                                                       │                  │
                                                       ▼                  ▼
                                              ProfileResult        ProfileResult
                                                       │                  │
                                                       └────────┬─────────┘
                                                                ▼
                                                       [C3-A ReportGenerator]
                                                       baseline_store por environment
                                                                │
                                                                ▼
                                                       ExecutionReport
                                                                │
                                ┌───────────────────────────────┼──────────────┐
                                ▼                               ▼              ▼
                       [C2-A baseline_store              [C4-F live_tracker  [C4-A APIRouter]
                        save_run x N perfiles]            .complete]         retorna 200 al cliente
                                                                                  │
                                                                                  ▼
                                                                             Dashboard P3 → P4
                                                                              o agente CI/CD
                                                                              (UC4)

                                                                             S3 bucket
                                                                             `testpilot-screenshots`
                                                                             ◄── GET /v1/runs/{id}/screenshots/{path}
                                                                                  (proxy desde C4-A)
```

## Communication Patterns

- **Intra-proceso:** Llamadas de función directas en Python entre componentes backend. Sin mensajería ni RPC en MVP.
- **Async:** FlowRunner, flows, ApiRouter handlers son `async`. boto3 (síncrono) se ejecuta en ThreadPoolExecutor vía `loop.run_in_executor`.
- **HTTP same-origin:** Dashboard MD0 → API se resuelve por `/v1/*` desde el mismo host (FastAPI sirve estáticos del dashboard). Sin CORS en MVP.
- **Polling cooperativo:** Dashboard P3 hace `GET /v1/runs/{id}/status` cada 3s ± 500ms jitter. Sin WebSocket (decisión D-MD0-02).
- **Dependency Injection (FastAPI):** Services se inyectan vía `Depends(get_xxx)` — permite tests con mocks.
- **Protocol para desacoplamiento:** Endpoints dependen de `BaselineStore` (Protocol), no de la implementación concreta. Habilita migración a DynamoDB sin tocar endpoints.
- **Caché TTL:** EnvironmentRegistry (60s) y EnvironmentResolver (5min) usan `cachetools.TTLCache` thread-safe.
- **Logs estructurados:** todos los componentes usan `logging.getLogger(__name__)` con `RedactingJsonFormatter` (salida JSON a stdout → CloudWatch via awslogs driver).

## Cambios en Código Existente

| Archivo existente | Tipo de cambio | Qué cambia |
|-------------------|----------------|------------|
| `src/agents/translator.py` | Minor | Importa `SyntheticUserConfig` de `src/models`; usa constante `CLAUDE_MODEL = "claude-haiku-4-5-20251001"`. Queda como funcionalidad opcional — no es entrada principal del POST /v1/run |
| `src/api/main.py` | **MAJOR** | Reescrito: 13 endpoints (vs 3 anteriores), 6 services nuevos (Registry, Resolver, SecretsClient, RunOrchestrator, LiveStatusTracker, DashboardStaticService), 2 middlewares (SecurityHeaders, RequestLogging), exception handlers globales, mount de StaticFiles para dashboard |
| `src/agents/__init__.py` | Patch | Sin cambio de lógica |
| `src/api/__init__.py` | Patch | Sin cambio de lógica |
| `tests/test_translator.py` | Minor | Actualizar mocks para el nuevo formato de `SyntheticUserConfig` (sin credenciales) |
| `tests/test_schemas.py` | **MAJOR** | Schema `synthetic-user-config.schema.json` cambia substancialmente (campos eliminados/agregados) — el test debe actualizarse |
| `tests/test_api.py` | **NUEVO** | Tests por endpoint con FastAPI TestClient |

## Archivos nuevos en código

| Archivo | Unidad |
|---|---|
| `pyproject.toml` | U0 |
| `src/models.py` (16 modelos) | U0 |
| `Dockerfile` (multi-stage) | U0 |
| `.dockerignore` | U0 |
| `src/executor/profiles/{mobile_co,desktop_co,desktop_ec}.py` | U1 |
| `src/executor/selectors.py` | U1 |
| `src/executor/auth/shopper_login.py` | U1 |
| `src/executor/flows/{checkout_full,checkout_card_declined}.py` | U1 |
| `src/executor/runner.py` | U1 |
| `src/baseline/baseline_manager.py` | U2 |
| `src/reporter/report_generator.py` | U3 |
| `src/api/{auth,deps,middleware,exceptions}.py` | U4 |
| `src/api/routers/{health,environments,runs,screenshots}.py` | U4 |
| `src/api/services/{environment_registry,environment_resolver,secrets_manager,run_orchestrator,live_status_tracker}.py` | U4 |
| `src/dashboard/` (Vite + React + TS + Tailwind + 5 pantallas + componentes + hooks) | MD0 |
