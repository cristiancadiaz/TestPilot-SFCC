# API Documentation — TestPilot SFCC

## REST APIs (Implemented)

### POST /v1/run
- **Method**: POST
- **Path**: /v1/run
- **Purpose**: Iniciar una ejecución de testing con usuarios sintéticos
- **Status**: Implementado (valida y retorna "queued"; ejecución real pendiente)
- **Request Body** (`application/json`):
  ```json
  {
    "testRunId": "550e8400-e29b-41d4-a716-446655440000",
    "environment_id": "staging",
    "products": [
      { "search_term": "camiseta negra talla M", "validate_variant": true }
    ],
    "flows": ["checkout_full"],
    "profiles": ["desktop_co"],
    "screenshot_on_success": true,
    "screenshot_on_error": true,
    "timeout": 60000
  }
  ```
  > **Nota**: Las credenciales NO van en el payload. El backend resuelve automáticamente `env_access_credentials` (testpilot/{env}/env-access) y `shopper_credentials` (testpilot/{env}/shopper) desde AWS Secrets Manager.
- **Response 200 OK**:
  ```json
  {
    "testRunId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "success",
    "trafficLight": "green"
  }
  ```
- **Response 404 Not Found**: `{"error_code": "environment_not_found"}` si `environment_id` no está registrado en el Environment Registry
- **Response 422 Unprocessable Entity**: Array de errores Pydantic con loc, msg, type
- **Validation Rules**:
  - `testRunId`: UUID v4 válido (36 chars)
  - `environment_id`: enum — solo `"sandbox"`, `"development"`, `"staging"` (registrados en Environment Registry)
  - `products`: array con al menos 1 ítem; cada ítem tiene `search_term` (string) y `validate_variant` (boolean)
  - `flows`: array con al menos 1 ítem; solo `"checkout_full"` o `"checkout_card_declined"`
  - `profiles`: array con al menos 1 ítem; solo `"mobile_co"`, `"desktop_co"` o `"desktop_ec"`
  - `screenshot_on_success`, `screenshot_on_error`: boolean (default true ambos)
  - `timeout`: entre 30000 y 180000 ms (default 60000)

## REST APIs (Pending — per PRD M2)

### GET /v1/runs/{run_id}
- **Method**: GET
- **Path**: /v1/runs/{run_id}
- **Purpose**: Recuperar resultado de una ejecución específica
- **Status**: No implementado
- **Response 200**: ExecutionReport completo (ver specs/execution_report.json)
- **Response 404**: Run no encontrado

### GET /v1/runs/latest
- **Method**: GET
- **Path**: /v1/runs/latest
- **Purpose**: El agente CI/CD consulta el último resultado para decisión de auto-merge
- **Status**: No implementado
- **Query params**: `?profile=mobile_co` (opcional)
- **Response 200**: ExecutionReport + campo `age_seconds` + campo `ttl_ok` (bool)

### GET /v1/runs (aggregate)
- **Method**: GET
- **Path**: /v1/runs
- **Purpose**: Historial diario para Tech Lead (PRD S2)
- **Status**: No implementado
- **Query params**: `?since=2026-05-13&aggregate=daily`
- **Response 200**: Array de resúmenes diarios con conteos verde/amarillo/rojo

## Internal APIs (Python Modules)

### src/agents/translator.py

#### translate(prompt: str) -> SyntheticUserConfig
- **Parameters**: `prompt` — instrucción en lenguaje natural
- **Returns**: `SyntheticUserConfig` Pydantic model validado
- **Raises**: `TranslatorError` si Claude API falla, JSON inválido, o schema inválido
- **Behavior**: 3 reintentos ante JSON parse errors; no reintenta en errores de schema

#### _validate_config(config: dict) -> SyntheticUserConfig
- **Parameters**: `config` — dict crudo del LLM
- **Returns**: `SyntheticUserConfig` validado
- **Raises**: `TranslatorError` si falla jsonschema.validate() o Pydantic
- **Side effect**: Traduce NL a SyntheticUserConfig validado; ya NO asigna `email` ni `storefrontUrl` — el ambiente se especifica vía `environment_id`

#### _build_prompt(prompt: str) -> str
- **Parameters**: `prompt` — instrucción usuario
- **Returns**: String con system prompt + lista de flows y profiles válidos

#### _load_schema() -> dict
- **Parameters**: ninguno
- **Returns**: JSON Schema dict desde `specs/synthetic_user_config.json`

## Data Models

### SyntheticUserConfig (specs/synthetic_user_config.json + Pydantic)
| Campo | Tipo | Requerido | Validación |
|-------|------|-----------|------------|
| testRunId | string (UUID) | Sí | Formato UUID v4 |
| environment_id | string (enum) | Sí | `sandbox`, `development` o `staging` |
| products | array | Sí | Al menos 1 ítem con `search_term` (string) + `validate_variant` (boolean) |
| flows | array (enum) | Sí | Uno o más de: `checkout_full`, `checkout_card_declined` |
| profiles | array (enum) | Sí | Uno o más de: `mobile_co`, `desktop_co`, `desktop_ec` |
| screenshot_on_success | boolean | No | default true |
| screenshot_on_error | boolean | No | default true |
| timeout | integer | No | 30000–180000, default 60000 |

> Los campos `storefrontUrl` y `email` no existen en `SyntheticUserConfig`. Las credenciales se resuelven internamente desde Secrets Manager vía `environment_id`.

### ExecutionReport (specs/execution_report.json)
| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| testRunId | string | Sí | UUID de la ejecución |
| status | string (enum) | Sí | `success`, `failed`, `error` |
| trafficLight | string (enum) | Sí | `green`, `yellow`, `red` |
| startedAt | string (datetime) | Sí | ISO 8601 |
| finishedAt | string (datetime) | Sí | ISO 8601 |
| durationMs | integer | No | Duración total en ms |
| steps | array | Sí | Lista de StepResult |
| config | object | Sí | flow, profile, storefrontUrl originales |
| baselineComparison | object | No | p95BaselineMs, percentDiff, bootstrapMode |

### StepResult (dentro de ExecutionReport.steps[])
| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| name | string | Sí | Nombre del paso (e.g., navigate_to_store) |
| status | string (enum) | Sí | `success`, `failed`, `skipped` |
| durationMs | integer | Sí | Duración del paso |
| error | string | No | Mensaje de error si falló |
| screenshot | string (URI) | No | URL S3 (solo fallo + paso final) |

### RunResponse (src/api/main.py)
| Campo | Tipo | Descripción |
|-------|------|-------------|
| testRunId | string | UUID de la ejecución aceptada |
| status | string | Siempre "queued" |
