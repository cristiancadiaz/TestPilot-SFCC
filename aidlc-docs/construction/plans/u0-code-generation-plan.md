# U0 Setup Base — Code Generation Plan

## Unit Context
- **Tipo**: Brownfield (modificación de código existente + creación de archivos nuevos)
- **Workspace root**: `F:\Development_Projects\IA\06_testing_sintetico`
- **Python**: 3.12
- **Stories cubiertas**: RF-01, RF-02, RF-03, RNF-01, RNF-08, RNF-10

## Dependencies
Ninguna. U0 es prerrequisito de todas las demás unidades.

## Steps

### Step 1: Crear `pyproject.toml` [x]
- **Acción**: CREATE
- **Archivo**: `pyproject.toml` (workspace root)
- **Contenido**:
  - `[project]` con `name`, `version = "0.1.0"`, `requires-python = ">=3.12"`
  - Dependencias directas con versiones pinned: `fastapi`, `uvicorn[standard]`, `pydantic`, `anthropic`, `playwright`, `boto3`, `jsonschema`
  - `[project.optional-dependencies]` sección `dev`: `pytest`, `pytest-asyncio`, `pytest-playwright`, `hypothesis`, `mypy`, `ruff`, `httpx`
  - `[tool.ruff]` configurado: `line-length = 100`, rules mínimas, `target-version = "py312"`
  - `[tool.mypy]` con `strict = true`, `python_version = "3.12"`
  - `[tool.pytest.ini_options]` con `testpaths = ["tests"]`, `pythonpath = ["."]`, `asyncio_mode = "auto"`
- **RF cubierto**: RF-01
- **Criterio**: `ruff check .` no genera errores; `mypy src/` sin errores de configuración

### Step 2: Crear `src/models.py` [x]
- **Acción**: CREATE
- **Archivo**: `src/models.py`
- **Contenido** (en orden de dependencia):
  1. `TrafficLight(str, Enum)`: GREEN, YELLOW, RED
  2. `SyntheticUserConfig(BaseModel)`: con todos los field_validators (testRunId UUID, storefrontUrl http/https, email @testpilot.internal, flow Literal, profile Literal, timeout 30000–180000)
  3. `BrowserProfile(BaseModel)`: name, viewport_width, viewport_height, locale, user_agent, is_mobile
  4. `StepResult(BaseModel)`: name, status Literal, duration_ms, error Optional, screenshot_url Optional
  5. `FlowResult(BaseModel)`: flow_name, steps list[StepResult], duration_ms, orders_created: int = 0
  6. `ProfileResult(BaseModel)`: profile BrowserProfile, flow_result FlowResult
  7. `RunRecord(BaseModel)`: run_id, profile_name, flow_name, duration_ms, status Literal, created_at datetime
  8. `BaselineComparison(BaseModel)`: p95_ms, current_ms, bootstrap_mode, runs_count
  9. `ExecutionReport(BaseModel)`: test_run_id, status, traffic_light, started_at, finished_at, duration_ms, steps, config dict, orders_created: int = 0, baseline_comparison Optional[BaselineComparison]
- **RF cubierto**: RF-02
- **Criterio**: `mypy src/models.py --strict` sin errores; todos los modelos instanciables desde tests

### Step 3: Crear `tests/test_models.py` [x]
- **Acción**: CREATE
- **Archivo**: `tests/test_models.py`
- **Contenido**:
  - `test_synthetic_user_config_valid`: instancia válida pasa
  - `test_synthetic_user_config_email_validation`: email sin @testpilot.internal falla
  - `test_synthetic_user_config_invalid_flow`: flow no en catálogo falla ValidationError
  - `test_synthetic_user_config_invalid_profile`: profile no en catálogo falla ValidationError
  - `test_synthetic_user_config_invalid_url`: URL sin http/https falla ValidationError
  - `test_synthetic_user_config_invalid_uuid`: testRunId no UUID falla ValidationError
  - `test_flow_result_orders_created_default`: FlowResult().orders_created == 0
  - `test_execution_report_orders_created_default`: ExecutionReport(...).orders_created == 0
  - `test_traffic_light_values`: TrafficLight tiene GREEN, YELLOW, RED
  - `test_browser_profile_valid`: BrowserProfile instancia correctamente
  - `test_run_record_valid`: RunRecord instancia correctamente con datetime timezone-aware
- **Criterio**: `pytest tests/test_models.py` pasa 100%

### Step 4: Actualizar `src/agents/translator.py` [x]
- **Acción**: MODIFY (brownfield)
- **Archivo**: `src/agents/translator.py`
- **Cambios**:
  1. Agregar `CLAUDE_MODEL = "claude-haiku-4-5-20251001"` como constante módulo (reemplaza string hardcoded en `client.messages.create`)
  2. Eliminar la clase `SyntheticUserConfig` local (líneas 20-27)
  3. Agregar import: `from src.models import SyntheticUserConfig`
  4. Verificar que `_validate_config` sigue funcionando con el import
- **RF cubierto**: RF-03
- **Criterio**: `test_translator.py` sigue pasando; `mypy src/agents/translator.py --strict` sin errores

### Step 5: Actualizar `src/api/main.py` [x]
- **Acción**: MODIFY (brownfield)
- **Archivo**: `src/api/main.py`
- **Cambios**:
  1. Eliminar la clase `SyntheticUserConfig` local (líneas 14-58) incluyendo todos sus field_validators y model_config
  2. Eliminar imports no usados: `Annotated`, `Field`, `field_validator` (si solo los usaba SyntheticUserConfig)
  3. Agregar import: `from src.models import SyntheticUserConfig`
  4. Verificar que `FlowType` y `ProfileType` se pueden eliminar (ahora están en SyntheticUserConfig de src/models)
  5. Mantener `RunResponse`, `app`, y el endpoint `run_test` sin cambios funcionales
- **RF cubierto**: RF-02 (deduplicación)
- **Criterio**: `test_schemas.py` y tests de API existentes pasan; `mypy src/api/main.py --strict` sin errores

### Step 6: Crear `Dockerfile` [x]
- **Acción**: CREATE
- **Archivo**: `Dockerfile` (workspace root)
- **Contenido**:
  - FROM `mcr.microsoft.com/playwright/python:v1.44.0-jammy`
  - WORKDIR `/app`
  - COPY `pyproject.toml .`
  - RUN `pip install --no-cache-dir -e .`
  - COPY `src/ src/`
  - COPY `specs/ specs/`
  - RUN `playwright install chromium --with-deps`
  - USER no-root (pwuser o appuser)
  - EXPOSE 8000
  - CMD `["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]`
- **RNF cubierto**: RNF-08 (sin latest), SECURITY-12, SECURITY-13
- **Criterio**: `docker build -t testpilot-sfcc:local .` completa sin errores

### Step 7: Crear `.dockerignore` [x]
- **Acción**: CREATE
- **Archivo**: `.dockerignore` (workspace root)
- **Contenido**: `.env`, `.git`, `aidlc-docs/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `tests/`, `*.md` (excepto README si existe)
- **RNF cubierto**: SECURITY-13

### Step 8: Crear `aidlc-docs/construction/u0/code/code-summary.md` [x]
- **Acción**: CREATE
- **Archivo**: `aidlc-docs/construction/u0/code/code-summary.md`
- **Contenido**: Resumen de archivos creados/modificados, versiones usadas, decisiones relevantes

## Verificación final del criterio de completitud de U0

Cuando todos los steps estén completos:
```bash
ruff check .          # debe pasar sin errores
mypy src/             # debe pasar sin errores (--strict implícito en config)
pytest tests/         # test_models.py + test_schemas.py + test_translator.py deben pasar
docker build -t testpilot-sfcc:local .   # debe completar
```

## Traceability

| RF/RNF | Step |
|--------|------|
| RF-01 (pyproject.toml) | Step 1 |
| RF-02 (src/models.py unificado) | Step 2, 4, 5 |
| RF-03 (modelo Claude actualizado) | Step 4 |
| RNF-01 (credenciales en env vars) | Step 4 (translator usa os.getenv) |
| RNF-08 (versiones pinned, sin latest) | Step 1, Step 6 |
| RNF-10 (reproducibilidad) | Step 1, Step 6 |
