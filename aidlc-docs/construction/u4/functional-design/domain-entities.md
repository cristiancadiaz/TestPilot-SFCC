# Domain Entities — U4 API Endpoints (actualizado 2026-05-24)

## Módulo: `src/api/`

U4 **consume** modelos de U0 y **produce** responses HTTP. No define modelos de dominio propios — define modelos de **payload de request/response** específicos del API que no caben en `src/models.py` (los que viven en U0 son dominio compartido entre módulos; los de U4 son contratos de transporte HTTP).

---

## Modelos consumidos (de src/models — definidos en U0)

- `EnvironmentConfig` — request/response de CRUD environments
- `SyntheticUserConfig` — request body de POST /v1/run
- `ExecutionReport` — response body de POST /v1/run y GET /v1/runs/{id}
- `RunStatus` — response body de GET /v1/runs/{id}/status
- `ResolvedEnvironment` — uso interno (resolver → orchestrator → executor)
- `EnvironmentAccessCredentials` — uso interno
- `ShopperCredentials` — uso interno
- `RunRecord` — uso interno (baseline_store)

---

## Modelos específicos de transporte HTTP (definidos en `src/api/`)

### EnvironmentUpdateRequest
Subset de `EnvironmentConfig` con campos editables. NO incluye `environment_id` ni `created_at`.

```python
class EnvironmentUpdateRequest(BaseModel):
    display_name: str | None = None
    store_url: HttpUrl | None = None
    env_access_secret_path: str | None = Field(default=None, pattern=...)
    shopper_secret_path: str | None = Field(default=None, pattern=...)
    anti_bot_whitelisted: bool | None = None
    active: bool | None = None
```

Pydantic permite que cualquier subset sea válido (campos opcionales).

### ExecutionReportWithMeta
Extiende `ExecutionReport` con metadata para `GET /v1/runs/latest`.

```python
class ExecutionReportWithMeta(ExecutionReport):
    age_seconds: int
    ttl_ok: bool  # True si age_seconds < TTL_SECONDS (14400)
```

### RunListResponse
Wrapper de paginación para `GET /v1/runs`.

```python
class RunListItem(BaseModel):
    run_id: str
    environment_id: str
    display_name: str  # join con EnvironmentConfig
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    traffic_light: TrafficLight
    bootstrap_mode: bool
    profiles_executed: list[ProfileId]
    flows_executed: list[FlowName]
    orders_created: int = 0

class RunListResponse(BaseModel):
    items: list[RunListItem]
    page: int
    page_size: int
    total: int
    has_more: bool
```

### RunListQuery (parsed query params)
```python
class RunListQuery(BaseModel):
    environment_id: EnvironmentId | None = None
    traffic_light: TrafficLight | None = None
    flow: FlowName | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)
```

### ApiErrorResponse
```python
class ApiErrorResponse(BaseModel):
    error_code: str
    message: str
    details: dict | None = None
```

### HealthResponse
```python
class HealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy"]
    checks: dict[str, Literal["ok", "fail"]]
    version: str
    git_sha: str | None = None
```

---

## Excepciones de dominio (definidas en `src/api/exceptions.py`)

```python
class TestPilotApiError(Exception):
    """Base para todas las excepciones de la API."""
    status_code: int
    error_code: str

class EnvironmentNotFoundError(TestPilotApiError):
    status_code = 404
    error_code = "environment_not_found"

class EnvironmentInactiveError(TestPilotApiError):
    status_code = 409
    error_code = "environment_inactive"

class SecretNotFoundError(TestPilotApiError):
    status_code = 502
    error_code = "secret_not_found"

class RunNotFoundError(TestPilotApiError):
    status_code = 404
    error_code = "run_not_found"

class RunTimeoutError(TestPilotApiError):
    status_code = 504
    error_code = "run_timeout"

class InvariantViolatedError(TestPilotApiError):
    status_code = 500
    error_code = "invariant_violated"

class InvalidSecretPathError(TestPilotApiError):
    status_code = 422
    error_code = "invalid_secret_path"
```

**Mapeo a `ApiErrorResponse`:** un único exception handler convierte estas excepciones en responses estructuradas.

---

## Servicios internos (no exportados como API)

### EnvironmentRegistry
Repositorio CRUD sobre DynamoDB. Conceptual:
```python
class EnvironmentRegistry:
    def list(self, only_active: bool = False) -> list[EnvironmentConfig]: ...
    def get(self, environment_id: str) -> EnvironmentConfig | None: ...
    def create(self, config: EnvironmentConfig) -> EnvironmentConfig: ...
    def update(self, environment_id: str, updates: EnvironmentUpdateRequest) -> EnvironmentConfig: ...
    def deactivate(self, environment_id: str) -> None: ...
```

### EnvironmentResolver
Resuelve `environment_id` → `ResolvedEnvironment` (con credenciales). Caché TTL 5 min.

### SecretsManagerClient
Wrapper boto3 minimalista. Recupera secret como JSON parseado.

### RunOrchestrator
Lógica de `POST /v1/run`. Orquesta `resolver` + `executor` + `baseline_store` + `reporter` + `live_tracker`.

### LiveStatusTracker
Ring buffer in-memory de runs vivos. Sirve `GET /v1/runs/{id}/status`.

---

## Dependencies (FastAPI)

```python
# src/api/deps.py
async def verify_api_key(x_api_key: str = Header(...)) -> None: ...

def get_environment_registry() -> EnvironmentRegistry: ...
def get_environment_resolver() -> EnvironmentResolver: ...
def get_baseline_store() -> BaselineStore: ...
def get_live_tracker() -> LiveStatusTracker: ...
def get_orchestrator(
    resolver = Depends(get_environment_resolver),
    baseline = Depends(get_baseline_store),
    tracker = Depends(get_live_tracker),
) -> RunOrchestrator: ...
```

Inyección de dependencias permite tests con mocks.

---

## Estructura modular

```
src/api/
├── main.py                # FastAPI app + middleware + routers
├── deps.py                # Depends helpers
├── auth.py                # verify_api_key
├── middleware.py          # SecurityHeadersMiddleware
├── exceptions.py          # Exception classes + handler
├── routers/
│   ├── health.py
│   ├── environments.py
│   ├── runs.py
│   └── screenshots.py
└── services/
    ├── environment_registry.py
    ├── environment_resolver.py
    ├── secrets_manager.py
    ├── run_orchestrator.py
    └── live_status_tracker.py
```

---

## Resumen

U4 crece significativamente vs versión anterior:
- **Antes:** 3 endpoints, sin services dedicados, in-memory todo.
- **Ahora:** 13 endpoints, 5 services con responsabilidades claras, DynamoDB para environments + S3 para screenshots.

La explosión de superficie está justificada por:
1. Soporte completo al dashboard MD0 (5 pantallas).
2. Modelo de credenciales duales con resolución segura.
3. Endpoints en tiempo real e historial.
4. Healthcheck y observabilidad para ECS.
