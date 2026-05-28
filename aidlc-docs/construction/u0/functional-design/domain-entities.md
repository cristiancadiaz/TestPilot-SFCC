# Domain Entities — U0 Setup Base (actualizado 2026-05-24)

Modelos Pydantic en `src/models.py` — fuente única de verdad. **Cambio mayor vs versión anterior:** se agrega `EnvironmentConfig` con el modelo de **dos credenciales por ambiente** y `SyntheticUserConfig` se modifica para no transportar credenciales.

---

## 1. EnvironmentConfig (NUEVO — entidad central)

Representa un ambiente registrado (sandbox / development / staging). Almacenada en DynamoDB tabla `environments`. Gestionada vía dashboard MD0 y API U4.

```python
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from typing import Literal

EnvironmentId = Literal["sandbox", "development", "staging"]

class EnvironmentConfig(BaseModel):
    environment_id: EnvironmentId
    display_name: str = Field(min_length=3, max_length=128)
    store_url: HttpUrl  # https obligatorio — Pydantic valida scheme
    env_access_secret_path: str = Field(
        pattern=r"^testpilot/[a-z][a-z0-9_-]+/[a-z][a-z0-9_-]+$"
    )
    shopper_secret_path: str = Field(
        pattern=r"^testpilot/[a-z][a-z0-9_-]+/[a-z][a-z0-9_-]+$"
    )
    anti_bot_whitelisted: bool = False
    active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"frozen": False, "str_strip_whitespace": True}
```

**Invariantes:**
- `environment_id` es immutable post-creación (verificado en U4 update endpoint).
- `store_url` debe ser HTTPS (validador Pydantic `HttpUrl` con `scheme == "https"`).
- Los paths siguen patrón `testpilot/{env}/{purpose}` — facilita auditoría en Secrets Manager.

---

## 2. EnvironmentAccessCredentials (resuelto en runtime, NO persistido)

Modelo de credenciales para **autenticación al ambiente** (HTTP Basic Auth / proxy gate). Resuelto desde Secrets Manager justo antes de ejecutar un run. **Nunca persistido, nunca logueado.**

```python
class EnvironmentAccessCredentials(BaseModel):
    username: str
    password: str = Field(repr=False)  # no aparece en repr()/__str__()

    model_config = {"frozen": True}

    def __str__(self) -> str:
        return f"EnvironmentAccessCredentials(username={self.username}, password=***)"
```

**Notas:**
- `repr=False` en `password` → no aparece en logs si alguien loggea el objeto.
- `__str__` redactado explícitamente.
- `frozen=True` → inmutable tras construcción.

---

## 3. ShopperCredentials (resuelto en runtime, NO persistido)

Modelo de credenciales del **shopper SFCC registrado** que ejecuta el flow de compra.

```python
from pydantic import EmailStr

class ShopperCredentials(BaseModel):
    email: EmailStr
    password: str = Field(repr=False)

    model_config = {"frozen": True}

    def __str__(self) -> str:
        return f"ShopperCredentials(email={self.email}, password=***)"
```

**Invariante de negocio (validada en U1, no aquí):**
- El email DEBE terminar en `@testpilot.internal`. La validación vive en `src/executor/runner.py` antes de ejecutar el flow (assertion explícita). Aquí solo se valida formato.

---

## 4. ResolvedEnvironment (composición runtime)

Estructura que recibe el executor — agrupa la config del ambiente + ambas credenciales resueltas.

```python
class ResolvedEnvironment(BaseModel):
    config: EnvironmentConfig
    env_access: EnvironmentAccessCredentials
    shopper: ShopperCredentials

    model_config = {"frozen": True}
```

**Construido por:** U4 `EnvironmentResolver.resolve(environment_id)` → consulta DynamoDB para `EnvironmentConfig`, consulta Secrets Manager para ambas credenciales, devuelve `ResolvedEnvironment`.

**Consumido por:** U1 `run_profile(profile, flow_name, config, env: ResolvedEnvironment)`.

---

## 5. SyntheticUserConfig (MODIFICADO — sin credenciales)

Request body de `POST /v1/run`. **Cambio crítico:** ya no contiene `storefront_url` ni credenciales — solo `environment_id`. La resolución ocurre en backend.

```python
class ProductSpec(BaseModel):
    search_term: str = Field(min_length=2, max_length=128)
    validate_variant: bool = True

FlowName = Literal["checkout-full", "checkout-card-declined"]
ProfileId = Literal["mobile-co", "desktop-co", "desktop-ec"]

class SyntheticUserConfig(BaseModel):
    environment_id: EnvironmentId
    products: list[ProductSpec] = Field(min_length=1, max_length=10)
    flows: list[FlowName] = Field(min_length=1, max_length=2)
    profiles: list[ProfileId] = Field(min_length=1, max_length=3)
    screenshot_on_success: bool = True
    screenshot_on_error: bool = True

    @field_validator("screenshot_on_error")
    @classmethod
    def screenshot_on_error_must_be_true(cls, v: bool) -> bool:
        if not v:
            raise ValueError("screenshot_on_error must be True (audit invariant)")
        return v
```

**Cambios respecto a versión previa:**
| Antes | Ahora |
|---|---|
| `storefront_url: HttpUrl` | Eliminado — se resuelve desde `environment_id` |
| `email: str` | Eliminado — vive en Secrets Manager (ShopperCredentials) |
| `password: str` | Eliminado — vive en Secrets Manager |
| (sin `environment_id`) | `environment_id: EnvironmentId` requerido |
| (sin `products`) | `products: list[ProductSpec]` — soporte para múltiples productos por run |
| `flow: str` (singular) | `flows: list[FlowName]` (múltiple) |
| (sin perfiles explícitos) | `profiles: list[ProfileId]` — control fino de qué perfiles ejecutar |

---

## 6. BrowserProfile (cambio mínimo: perfil `desktop-ec` reemplaza `mobile-mx`)

```python
class BrowserProfile(BaseModel):
    name: ProfileId  # mobile-co | desktop-co | desktop-ec
    viewport_width: int
    viewport_height: int
    locale: str
    user_agent: str
    is_mobile: bool
```

**Catálogo actualizado:**
- `mobile-co`: 390×844, es-CO, Chrome mobile UA
- `desktop-co`: 1440×900, es-CO, Chrome desktop UA
- `desktop-ec`: 1280×800, es-EC, Chrome desktop UA (reemplaza `mobile-mx` de versión previa — alineado con prompt actualizado del proyecto)

---

## 7. StepResult (modificación menor)

Se agrega `screenshot_state` opcional — la disciplina de screenshots cambió (ahora se capturan en cada paso según flags, no solo en fallo+final).

```python
class StepResult(BaseModel):
    name: str
    status: Literal["success", "failed", "skipped"]
    duration_ms: int
    error: str | None = None
    screenshot_url: str | None = None  # path relativo en S3 (o local en dev)
    screenshot_state: Literal["ok", "fail"] | None = None  # nuevo
```

---

## 8. FlowResult, ProfileResult, BaselineComparison, TrafficLight, RunRecord, ExecutionReport

Sin cambios estructurales mayores. Se documentan para completitud:

```python
class FlowResult(BaseModel):
    flow_name: FlowName
    status: Literal["success", "failed", "error"]
    steps: list[StepResult]
    duration_ms: int
    orders_created: int = 0  # invariante: siempre 0

class ProfileResult(BaseModel):
    profile: BrowserProfile
    flow_result: FlowResult
    traffic_light: "TrafficLight"

class TrafficLight(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"

class BaselineComparison(BaseModel):
    p95_ms: int
    current_ms: int
    bootstrap_mode: bool
    runs_count: int

class RunRecord(BaseModel):
    run_id: str
    environment_id: EnvironmentId
    profile_name: ProfileId
    flow_name: FlowName
    duration_ms: int
    status: Literal["success", "failed", "error"]
    created_at: datetime

class RunState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ProfileLiveStatus(BaseModel):
    profile_id: ProfileId
    state: Literal["pending", "running", "success", "failed"]
    current_step: str | None
    steps_completed: int
    steps_total: int
    duration_ms: int

class RunStatus(BaseModel):  # NUEVO — para vista en tiempo real (MD0 P3)
    run_id: str
    state: RunState
    started_at: datetime
    environment_id: EnvironmentId
    profiles: list[ProfileLiveStatus]

class ExecutionReport(BaseModel):
    run_id: str
    environment_id: EnvironmentId
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    traffic_light: TrafficLight
    bootstrap_mode: bool
    orders_created: int = 0
    profile_results: list[ProfileResult]
    baseline_comparison: BaselineComparison | None = None
```

---

## Resumen de modelos en `src/models.py`

| Modelo | Persistido | Nuevo en esta versión |
|---|---|---|
| `EnvironmentConfig` | DynamoDB `environments` | ✅ |
| `EnvironmentAccessCredentials` | NO (runtime) | ✅ |
| `ShopperCredentials` | NO (runtime) | ✅ |
| `ResolvedEnvironment` | NO (runtime) | ✅ |
| `SyntheticUserConfig` | NO (efímero) | Modificado (sin credenciales) |
| `BrowserProfile` | NO (estático) | Catálogo actualizado |
| `StepResult` | DynamoDB `runs` (anidado) | Campo nuevo `screenshot_state` |
| `FlowResult` | DynamoDB `runs` (anidado) | — |
| `ProfileResult` | DynamoDB `runs` (anidado) | — |
| `TrafficLight` (enum) | — | — |
| `BaselineComparison` | DynamoDB `runs` (anidado) | — |
| `RunRecord` | DynamoDB `runs` | Campo nuevo `environment_id` |
| `RunState` (enum) | — | ✅ |
| `ProfileLiveStatus` | DynamoDB `runs` (en runs vivos) | ✅ |
| `RunStatus` | NO (proyección) | ✅ |
| `ExecutionReport` | DynamoDB `runs` + S3 screenshots | Campo nuevo `environment_id`, `bootstrap_mode` top-level |

---

## Referencias cruzadas

- `inception/application-design/error-taxonomy.md` — semántica completa de `status` y mapeo a HTTP/TrafficLight.
- `inception/application-design/env-vars-catalog.md` — env vars consumidas por U4 para construir clientes boto3.
- `construction/md0/functional-design/domain-entities.md` — proyección TypeScript de estos modelos para el frontend.
