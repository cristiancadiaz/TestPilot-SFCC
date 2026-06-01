# Component Methods — TestPilot SFCC (actualizado 2026-05-24)

> Las firmas son definitivas. La lógica detallada de cada método se define en Functional Design (Construction Phase).
>
> **Cambio mayor 2026-05-24:** agregados modelos del nuevo modelo de credenciales duales, modelos de Environment Registry y modelos del dashboard. Firmas de executor actualizadas para recibir `ResolvedEnvironment`. Agregadas firmas de los 5 servicios nuevos de U4.

---

## C0-A: SharedModels — src/models.py

```python
from pydantic import BaseModel, Field, HttpUrl, EmailStr, field_validator
from datetime import datetime
from typing import Literal
from enum import Enum

# ---------- Enums / Literals (catálogos cerrados) ----------
EnvironmentId = Literal["sandbox", "development", "staging"]
FlowName = Literal["checkout_full", "checkout_card_declined"]
ProfileId = Literal["mobile_co", "desktop_co", "desktop_ec"]

class TrafficLight(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"

class RunState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

# ---------- Environment Registry (★ NUEVO) ----------
class EnvironmentConfig(BaseModel):
    environment_id: EnvironmentId
    display_name: str = Field(min_length=3, max_length=128)
    store_url: HttpUrl  # HTTPS obligatorio
    env_access_secret_path: str = Field(pattern=r"^testpilot/[a-z][a-z0-9_-]+/[a-z][a-z0-9_-]+$")
    shopper_secret_path: str = Field(pattern=r"^testpilot/[a-z][a-z0-9_-]+/[a-z][a-z0-9_-]+$")
    anti_bot_whitelisted: bool = False
    active: bool = True
    created_at: datetime
    updated_at: datetime

class EnvironmentAccessCredentials(BaseModel):
    """Credenciales para HTTP Basic Auth contra la puerta del ambiente."""
    username: str
    password: str = Field(repr=False)

    model_config = {"frozen": True}

    def __str__(self) -> str:
        return f"EnvironmentAccessCredentials(username={self.username}, password=***)"

class ShopperCredentials(BaseModel):
    """Credenciales del shopper SFCC registrado que ejecuta el checkout."""
    email: EmailStr  # debe terminar en @testpilot.internal (validado en runner)
    password: str = Field(repr=False)

    model_config = {"frozen": True}

    def __str__(self) -> str:
        return f"ShopperCredentials(email={self.email}, password=***)"

class ResolvedEnvironment(BaseModel):
    """Composición runtime — el executor recibe esto, NO el SyntheticUserConfig con credenciales."""
    config: EnvironmentConfig
    env_access: EnvironmentAccessCredentials
    shopper: ShopperCredentials

    model_config = {"frozen": True}

# ---------- SyntheticUserConfig (MODIFICADO — sin credenciales) ----------
class ProductSpec(BaseModel):
    search_term: str = Field(min_length=2, max_length=128)
    validate_variant: bool = True

class SyntheticUserConfig(BaseModel):
    environment_id: EnvironmentId
    products: list[ProductSpec] = Field(min_length=1, max_length=10)
    flows: list[FlowName] = Field(min_length=1, max_length=2)
    profiles: list[ProfileId] = Field(min_length=1, max_length=3)
    capture_intermediate_screenshots: bool = False  # invariante de costo — debe ser False en MVP

    @field_validator("capture_intermediate_screenshots")
    @classmethod
    def intermediate_screenshots_must_be_false(cls, v: bool) -> bool:
        if v:
            raise ValueError("capture_intermediate_screenshots must be False in MVP")
        return v

# ---------- Browser y ejecución ----------
class BrowserProfile(BaseModel):
    name: ProfileId
    viewport_width: int
    viewport_height: int
    locale: str
    user_agent: str
    is_mobile: bool

class StepResult(BaseModel):
    name: str
    status: Literal["success", "failed", "skipped"]
    duration_ms: int
    error: str | None = None
    screenshot_url: str | None = None  # path S3 relativo
    screenshot_state: Literal["fail", "final"] | None = None

class FlowResult(BaseModel):
    flow_name: FlowName
    status: Literal["success", "failed", "error"]
    steps: list[StepResult]
    duration_ms: int
    orders_created: int = 0  # invariante

class ProfileResult(BaseModel):
    profile: BrowserProfile
    flow_result: FlowResult
    traffic_light: TrafficLight

class BaselineComparison(BaseModel):
    p95_ms: int
    current_ms: int
    bootstrap_mode: bool
    runs_count: int

class RunRecord(BaseModel):
    run_id: str
    environment_id: EnvironmentId  # ★ NUEVO en clave compuesta del baseline
    profile_name: ProfileId
    flow_name: FlowName
    duration_ms: int
    status: Literal["success", "failed", "error"]
    created_at: datetime

# ---------- Live status (★ NUEVO — para dashboard P3) ----------
class ProfileLiveStatus(BaseModel):
    profile_id: ProfileId
    state: Literal["pending", "running", "success", "failed"]
    current_step: str | None
    steps_completed: int
    steps_total: int
    duration_ms: int

class RunStatus(BaseModel):
    run_id: str
    state: RunState
    started_at: datetime
    environment_id: EnvironmentId
    profiles: list[ProfileLiveStatus]

# ---------- ExecutionReport ----------
class ExecutionReport(BaseModel):
    run_id: str
    environment_id: EnvironmentId      # ★ NUEVO top-level
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    traffic_light: TrafficLight
    bootstrap_mode: bool                # ★ NUEVO top-level
    orders_created: int = 0
    profile_results: list[ProfileResult]
    baseline_comparison: BaselineComparison | None = None
```

---

## C1-E: FlowRunner — src/executor/runner.py

```python
async def run_profile(
    profile: BrowserProfile,
    flow_name: FlowName,
    config: SyntheticUserConfig,
    env: ResolvedEnvironment,         # ★ NUEVO — reemplaza storefront_url
    run_id: str,
) -> ProfileResult:
    """
    Lanza browser con perfil + http_credentials (env.env_access).
    Ejecuta env_access_auth + shopper_login + flow funcional.
    Garantiza orders_created=0 (assertion).
    Cierra browser en finally (NFR-R2).
    Captura InfrastructureError y retorna ProfileResult con status=error + YELLOW.
    """

# Función auxiliar interna
def _get_flow_runner(flow_name: FlowName) -> Callable:
    """Retorna la función run() del flow correspondiente al flow_name."""

def _initial_traffic_light(flow_result: FlowResult) -> TrafficLight:
    """GREEN si success; YELLOW si error (infra); RED si failed (app)."""
```

---

## C1-C/D: Flows — src/executor/flows/checkout_full.py y checkout_card_declined.py

```python
async def run(
    page: Page,
    config: SyntheticUserConfig,
    env: ResolvedEnvironment,         # ★ NUEVO — reemplaza storefront_url
    run_id: str,
    profile_id: str,
) -> FlowResult:
    """
    Ejecuta los 8 pasos funcionales del flow (env_access_auth y shopper_login
    ya se ejecutaron en runner.run_profile antes de invocar este flow).
    Retorna FlowResult con steps, duration_ms, orders_created=0.
    """

# Funciones privadas de cada paso (internas al módulo)
async def _search_product(page: Page, search_term: str) -> StepResult: ...
async def _category_page(page: Page) -> StepResult: ...
async def _pdp_variant_select(page: Page, validate_variant: bool) -> StepResult: ...
async def _add_to_cart(page: Page) -> StepResult: ...
async def _mini_cart_validation(page: Page) -> StepResult: ...
async def _checkout_shipping(page: Page) -> StepResult: ...
async def _checkout_payment(page: Page) -> StepResult: ...           # solo checkout_full
async def _payment_failure_validation(page: Page) -> StepResult: ... # solo checkout_full
async def _checkout_payment_declined(page: Page) -> StepResult: ...  # solo checkout_card_declined
async def _verify_decline_message(page: Page) -> StepResult: ...     # solo checkout_card_declined
```

---

## C1-Auth (★ NUEVO): shopper_login — src/executor/auth/shopper_login.py

```python
async def shopper_login(
    page: Page,
    credentials: ShopperCredentials,
    config: SyntheticUserConfig,
    run_id: str,
    profile_id: str,
    flow_name: FlowName,
) -> StepResult:
    """
    Form interactivo (page.fill + page.click) contra LOGIN_* selectors.
    Espera LOGIN_MY_ACCOUNT_INDICATOR para confirmar éxito.
    Status="failed" si selector no aparece (bug de la tienda, no infra).
    """
```

---

## C2-A/B/C: BaselineManager — src/baseline/baseline_manager.py

```python
class BaselineStore(Protocol):
    def save_run(self, run: RunRecord) -> None: ...
    
    def get_last_n_runs(
        self,
        environment_id: str,  # ★ NUEVO en clave compuesta
        profile: str,
        flow: str,
        n: int,
        status: Literal["success", "failed", "error"] | None = None,
    ) -> list[RunRecord]: ...
    
    def get_run(self, run_id: str) -> RunRecord | None: ...
    
    def list_runs(  # ★ NUEVO — para dashboard P5
        self,
        environment_id: str | None = None,
        traffic_light: Literal["green", "yellow", "red"] | None = None,
        flow: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[RunRecord], int]: ...  # (items, total_count)

class InMemoryBaselineStore:
    # implementa BaselineStore con clave (environment_id, profile, flow)
    ...

# Funciones puras de cálculo (módulo-level, no en clase — facilita PBT)
def calculate_p95(runs: list[RunRecord]) -> int:
    """P95 de duration_ms de runs success. Invariante: min <= p95 <= max."""

def is_bootstrap_mode(runs: list[RunRecord]) -> bool:
    """True si len(success_runs) < BOOTSTRAP_MIN_RUNS (14)."""

def compute_traffic_light(current_ms: int, p95_ms: int, bootstrap: bool) -> TrafficLight:
    """
    bootstrap=True → GREEN
    current > p95 * 1.5 → RED
    current > p95 * 1.2 → YELLOW
    otherwise → GREEN
    """
```

---

## C3-A/B: ReportGenerator — src/reporter/report_generator.py

```python
def generate_report(
    profile_results: list[ProfileResult],
    baseline_store: BaselineStore,
    config: SyntheticUserConfig,
    run_id: str,
    env: ResolvedEnvironment,         # ★ NUEVO — necesario para baseline por ambiente
    started_at: datetime,
) -> ExecutionReport:
    """
    Construye ExecutionReport completo con environment_id top-level + bootstrap_mode top-level.
    Garantiza orders_created=0 vía assert (BR-U3-01).
    Consulta baseline pasando environment_id (BR-U3-02).
    Persiste RunRecord por cada perfil (BR-U3-09).
    Valida resultado contra specs/execution_report.json.
    """

def to_json_dict(report: ExecutionReport) -> dict:
    """Serializa a camelCase. Valida contra JSON Schema."""

def to_markdown(report: ExecutionReport) -> str:
    """Markdown con emoji de semáforo, banner orders_created=0, tabla por perfil."""

# Helpers internos
def _determine_overall_status(profile_results) -> Literal["success", "failed", "error"]: ...
def _worst_traffic_light(lights: list[TrafficLight]) -> TrafficLight: ...
def _emoji_for_light(light: TrafficLight) -> str: ...
def _format_duration(ms: int) -> str: ...
```

---

## C4-A: APIRouter — src/api/main.py + routers/

```python
# ---------- Auth dependency ----------
async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    """Valida X-API-Key contra TESTPILOT_API_KEY con hmac.compare_digest (timing-safe)."""

# ---------- POST /v1/run ----------
@app.post("/v1/run", response_model=ExecutionReport, status_code=200)
async def run_test(
    config: SyntheticUserConfig,
    orchestrator: RunOrchestrator = Depends(get_orchestrator),
    _: None = Depends(verify_api_key),
) -> ExecutionReport: ...

# ---------- GET /v1/runs/{run_id} ----------
@app.get("/v1/runs/{run_id}", response_model=ExecutionReport)
async def get_run(run_id: UUID, _: None = Depends(verify_api_key)) -> ExecutionReport: ...

# ---------- GET /v1/runs/latest ----------
@app.get("/v1/runs/latest", response_model=ExecutionReportWithMeta)
async def get_latest_run(_: None = Depends(verify_api_key)) -> ExecutionReportWithMeta: ...

class ExecutionReportWithMeta(ExecutionReport):
    age_seconds: int
    ttl_ok: bool

# ---------- GET /v1/runs/{id}/status (★ NUEVO) ----------
@app.get("/v1/runs/{run_id}/status", response_model=RunStatus)
async def get_run_status(
    run_id: UUID,
    tracker: LiveStatusTracker = Depends(get_live_tracker),
    _: None = Depends(verify_api_key),
) -> RunStatus: ...

# ---------- GET /v1/runs (★ NUEVO — historial) ----------
@app.get("/v1/runs", response_model=RunListResponse)
async def list_runs(
    query: RunListQuery = Depends(),  # query params
    baseline: BaselineStore = Depends(get_baseline_store),
    _: None = Depends(verify_api_key),
) -> RunListResponse: ...

# ---------- Environment Registry (★ NUEVO) ----------
@app.post("/v1/environments", response_model=EnvironmentConfig, status_code=201)
async def create_environment(
    config: EnvironmentConfig,
    registry: EnvironmentRegistry = Depends(get_environment_registry),
    secrets: SecretsManagerClient = Depends(get_secrets_client),
    _: None = Depends(verify_api_key),
) -> EnvironmentConfig: ...

@app.get("/v1/environments", response_model=list[EnvironmentConfig])
async def list_environments(
    only_active: bool = False,
    registry: EnvironmentRegistry = Depends(get_environment_registry),
    _: None = Depends(verify_api_key),
) -> list[EnvironmentConfig]: ...

@app.get("/v1/environments/{environment_id}", response_model=EnvironmentConfig)
async def get_environment(
    environment_id: EnvironmentId,
    registry: EnvironmentRegistry = Depends(get_environment_registry),
    _: None = Depends(verify_api_key),
) -> EnvironmentConfig: ...

@app.put("/v1/environments/{environment_id}", response_model=EnvironmentConfig)
async def update_environment(
    environment_id: EnvironmentId,
    updates: EnvironmentUpdateRequest,
    registry: EnvironmentRegistry = Depends(get_environment_registry),
    _: None = Depends(verify_api_key),
) -> EnvironmentConfig: ...

@app.delete("/v1/environments/{environment_id}", status_code=204)
async def deactivate_environment(
    environment_id: EnvironmentId,
    registry: EnvironmentRegistry = Depends(get_environment_registry),
    _: None = Depends(verify_api_key),
) -> None: ...

# ---------- Screenshots proxy (★ NUEVO) ----------
@app.get("/v1/runs/{run_id}/screenshots/{path:path}")
async def get_screenshot(
    run_id: UUID,
    path: str,  # validado por regex
    _: None = Depends(verify_api_key),
) -> Response: ...

# ---------- Health (sin auth) ----------
@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse: ...
```

---

## C4-B: EnvironmentRegistry — src/api/services/environment_registry.py (★ NUEVO)

```python
class EnvironmentRegistry:
    def __init__(self, table_name: str) -> None: ...
    
    def list(self, only_active: bool = False) -> list[EnvironmentConfig]: ...
    def get(self, environment_id: str) -> EnvironmentConfig | None: ...
    def create(self, config: EnvironmentConfig) -> EnvironmentConfig: ...
    def update(self, environment_id: str, updates: EnvironmentUpdateRequest) -> EnvironmentConfig: ...
    def deactivate(self, environment_id: str) -> None: ...
    def invalidate(self, environment_id: str) -> None:
        """Limpia caché del registry y notifica al resolver."""
```

---

## C4-C: EnvironmentResolver — src/api/services/environment_resolver.py (★ NUEVO)

```python
class EnvironmentResolver:
    def __init__(self, registry: EnvironmentRegistry, secrets: SecretsManagerClient) -> None: ...
    
    def resolve(self, environment_id: str) -> ResolvedEnvironment:
        """
        Cache hit (TTL 5min) → return.
        Si falla cualquier paso: raise excepción tipada
        (EnvironmentNotFoundError | EnvironmentInactiveError | SecretNotFoundError | InvalidSecretPathError).
        """
    
    def invalidate(self, environment_id: str) -> None: ...
```

---

## C4-D: SecretsManagerClient — src/api/services/secrets_manager.py (★ NUEVO)

```python
class SecretsManagerClient:
    def __init__(self) -> None:
        self._client = boto3.client("secretsmanager")
    
    def get_json(self, secret_path: str) -> dict:
        """Recupera secret y parsea como JSON. Lanza ClientError si falla."""
```

---

## C4-E: RunOrchestrator — src/api/services/run_orchestrator.py (★ NUEVO)

```python
class RunOrchestrator:
    def __init__(
        self,
        resolver: EnvironmentResolver,
        baseline_store: BaselineStore,
        live_tracker: LiveStatusTracker,
        max_concurrent: int = 3,
    ) -> None: ...
    
    async def run(self, config: SyntheticUserConfig) -> ExecutionReport:
        """
        Orquesta: resolve → live_tracker.start → asyncio.gather con semaphore →
        generate_report → save_run → live_tracker.complete.
        Watchdog: asyncio.wait_for(timeout=RUN_TIMEOUT_SECONDS=1800).
        """
```

---

## C4-F: LiveStatusTracker — src/api/services/live_status_tracker.py (★ NUEVO)

```python
class LiveStatusTracker:
    """Ring buffer in-memory de hasta 100 runs vivos. Thread-safe con Lock."""
    
    def __init__(self, max_runs: int = 100) -> None: ...
    def start(self, run_id: str, env_id: str, started_at: datetime, profile_ids: list[str]) -> None: ...
    def update_profile(self, run_id: str, profile_id: str, **kwargs) -> None: ...
    def complete(self, run_id: str, traffic_light: TrafficLight) -> None: ...
    def fail(self, run_id: str, error: str) -> None: ...
    def get(self, run_id: str) -> RunStatus | None: ...
```

---

## C-D0: DashboardApp — src/dashboard/ (★ NUEVO)

```typescript
// Componentes principales (ver construction/md0/ para detalle)
function App(): JSX.Element { /* routing entre las 5 pantallas */ }
function EnvironmentsPage(): JSX.Element { /* P1 - CRUD ambientes */ }
function NewRunPage(): JSX.Element { /* P2 - lanzar run */ }
function LiveRunPage(): JSX.Element { /* P3 - polling de estado */ }
function RunDetailPage(): JSX.Element { /* P4 - reporte completo */ }
function HistoryPage(): JSX.Element { /* P5 - historial filtrable */ }

// Hooks reutilizables
function usePolling<T>(fetcher: () => Promise<T>, intervalMs: number, shouldContinue: (data: T) => boolean): ...
function useEnvironments(): { environments, refetch, ... }
function useRunFilters(): { filters, updateFilter }

// API client
class ApiClient {
  constructor() { /* lee X-API-Key de sessionStorage */ }
  async fetch<T>(path: string, options?: RequestInit): Promise<T>
}

// Componentes UI
function TrafficLight({ color, size, bootstrapMode }): JSX.Element
function ScreenshotThumbnail({ url, alt }): JSX.Element
function StepErrorMessage({ error }): JSX.Element
```

---

## Resumen de modelos y métodos

| Categoría | Antes (2026-05-20) | Ahora (2026-05-24) |
|---|---|---|
| Modelos en `src/models.py` | 9 | **16** (+7 nuevos) |
| Servicios en U4 | 1 (APIRouter) | **6** (APIRouter + 5 services) |
| Endpoints públicos | 3 | **13** |
| Componente nuevo | — | **C-D0 DashboardApp** |
| Catálogo de naming | guion en strings (`mobile-co`) | **underscore en contrato y Python** (`mobile_co`, `mobile_co.py`) |
