# U0 Setup Base — Code Generation Plan

> 🔄 **Reconciliado 2026-06-03** a: (a) contrato `specs/` **v2** (realineación de alcance — flows de recorrido + `full_journey` + `mode`), (b) alcance **greenfield** (no existe scaffolding previo — Steps 4–5 originales diferidos a U4, igual que TASK-005), (c) workspace root actual, (d) imagen Docker alineada con TASK-002 (v1.48.0). Checkboxes reseteados: el plan anterior los tenía marcados sin que exista código en este repo.

## Unit Context
- **Tipo**: Greenfield (no hay código previo en este workspace)
- **Workspace root**: `F:\Development_Projects\IA\TestPilot-SFCC`
- **Python**: 3.12 (gestionado por `uv` — cpython 3.12.13 ya instalado)
- **Stories cubiertas**: RF-01, RF-02, RNF-01, RNF-08, RNF-10 (RF-03 diferido a U4 junto con el refactor del translator)
- **Task package**: `docs/tasks/` TASK-001..006 (TASK-005 diferida) — Linear CHR-5..CHR-9

## Dependencies
Ninguna. U0 es prerrequisito de todas las demás unidades. Prerrequisito de contrato CUMPLIDO: `specs/synthetic-user-config.schema.json` v2 (HITL aprobado 2026-06-03).

## Steps

### Step 1: Crear `pyproject.toml` [ ]  *(= TASK-001 · HITL: requiere confirmación humana)*
- **Acción**: CREATE
- **Archivo**: `pyproject.toml` (workspace root)
- **Contenido**:
  - `[project]` con `name`, `version = "0.1.0"`, `requires-python = ">=3.12"`
  - Dependencias directas con versiones pinned: `fastapi`, `uvicorn[standard]`, `pydantic`, `anthropic`, `playwright`, `boto3`, `jsonschema`
  - `[project.optional-dependencies]` sección `dev`: `pytest`, `pytest-asyncio`, `pytest-playwright`, `hypothesis`, `mypy`, `ruff`, `httpx`
  - `[tool.ruff]`: `line-length = 100`, reglas E/F/I/UP, `target-version = "py312"`
  - `[tool.mypy]`: `strict = true`, `python_version = "3.12"`
  - `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `pythonpath = ["."]`, `asyncio_mode = "auto"`
- **RF cubierto**: RF-01
- **Criterio**: `uv sync` instala sin errores; `uv run ruff check .` y `uv run mypy src/` corren sin errores de configuración

### Step 2: Crear `src/models.py` — espejo del contrato v2 [ ]  *(= TASK-003)*
- **Acción**: CREATE
- **Archivo**: `src/models.py` (+ `src/__init__.py`)
- **Contenido** (en orden de dependencia):
  1. `TrafficLight(str, Enum)`: GREEN, YELLOW, RED
  2. `Product(BaseModel)`: `search_term` (str, 2–128), `validate_variant` (bool = True)
  3. `RunOptions(BaseModel)`: `timeout_seconds` (int, 30–600, default 180), `capture_intermediate_screenshots` (Literal[False] = False — invariante de costo)
  4. `SyntheticUserConfig(BaseModel)` — **espeja `specs/synthetic-user-config.schema.json` v2** (`model_config = ConfigDict(extra="forbid")`):
     - `schema_version: Literal["v2"] = "v2"`
     - `environment_id: Literal["sandbox", "development", "staging"]` (production imposible)
     - `flows: list[FlowName]` — `FlowName = Literal["checkout_full", "checkout_card_declined", "search_and_filter", "browse_discounted_products", "pdp_validation", "cart_review", "full_journey"]`, 1–6 ítems, únicos. `full_journey` = alias de composición (lo expande el FlowCatalog en U5, no este modelo)
     - `mode: Literal["gate", "exploratory"] = "gate"` (C11: exploratorio nunca al baseline)
     - `profiles: list[Literal["mobile_co", "desktop_co", "desktop_ec"]]`, 1–3 ítems, únicos
     - `products: list[Product]`, 1–10 ítems
     - `options: RunOptions | None = None`
  5. `BrowserProfile`, `StepResult` (con `phase: Literal["setup","flow"] = "flow"`), `FlowResult` (`orders_created: int = 0`), `ProfileResult`, `RunRecord`, `BaselineComparison`, `ExecutionReport` (`test_run_id`, `mode`, `orders_created: int = 0`)
  - **Fuera de alcance U0**: campos `audit` y `network_summary` del report v2 — los agregan U6/U7
- **RF cubierto**: RF-02
- **Criterio**: `uv run mypy src/models.py` sin errores; los 4 ejemplos del schema v2 instancian sin error

### Step 3: Crear `tests/test_models.py` [ ]  *(= TASK-004)*
- **Acción**: CREATE
- **Archivo**: `tests/test_models.py` (+ `tests/__init__.py`)
- **Contenido**: la lista completa de tests de TASK-004 — incluye los de v2: `test_synthetic_user_config_schema_version_v2`, `test_synthetic_user_config_accepts_journey_flows`, `test_synthetic_user_config_mode`, bounds 1–6 de flows, `test_schema_examples_instantiate` (round-trip contra los ejemplos reales del schema), más los invariantes clásicos (nunca-producción, catálogo cerrado, screenshots const false, `orders_created=0`, timezone-aware)
- **Criterio**: `uv run pytest tests/test_models.py -v` 100% verde

### Step 4: Crear `Dockerfile` [ ]  *(= TASK-002 · gate de build pendiente de reinicio post-instalación de Docker)*
- **Acción**: CREATE
- **Archivo**: `Dockerfile` (workspace root)
- **Contenido**:
  - `FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy` (pinned — alinear con la versión de `playwright` del pyproject)
  - `WORKDIR /app` · `COPY pyproject.toml .` · `RUN pip install --no-cache-dir -e .`
  - `COPY src/ src/` · `COPY specs/ specs/` · `RUN playwright install chromium --with-deps`
  - Usuario **no-root** (`pwuser`) · `EXPOSE 8000` · `CMD ["uvicorn","src.api.main:app","--host","0.0.0.0","--port","8000"]`
  - Nota greenfield: `src/api/main.py` no existe aún (llega en U4) — el CMD es el entrypoint objetivo; el gate U0 valida `docker build` + imports, no la ejecución de la app
- **RNF cubierto**: RNF-08, SECURITY-12/13
- **Criterio**: `docker build -t testpilot-sfcc:local .` completa; `whoami` ≠ root

### Step 5: Crear `.dockerignore` [ ]  *(= TASK-002)*
- **Acción**: CREATE
- **Contenido**: `.env*`, `.git`, `aidlc-docs/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `tests/`, `.claude/`, `.ai/`, `.hardcore-ai/`, `docs/`
- **RNF cubierto**: SECURITY-13

### ~~Step 6: Actualizar `src/agents/translator.py`~~ — DIFERIDO a U4 *(= TASK-005 diferida)*
> El scaffolding (`translator.py`, `api/main.py`) no existe en este repo — no hay nada que deduplicar. La promoción del translator (RF-27, modelo `CLAUDE_MODEL`) llega con U4/U8.

### Step 7: Crear `aidlc-docs/construction/u0/code/code-summary.md` [ ]  *(= TASK-006)*
- **Acción**: CREATE/UPDATE
- **Contenido**: archivos creados, versiones usadas, decisiones, mapa RF/RNF → archivo/test, y el estado de los 4 gates (incluido `docker build` si quedó pendiente de entorno, marcado explícitamente)

## Verificación final del criterio de completitud de U0 (Gate 1 — TASK-006)

```bash
uv run ruff check .                       # exit 0
uv run mypy src/                          # exit 0
uv run pytest                             # exit 0 (test_models.py)
docker build -t testpilot-sfcc:local .    # exit 0 (pendiente de entorno hasta reinicio post-instalación)
```

## Traceability

| RF/RNF | Step |
|--------|------|
| RF-01 (pyproject.toml) | Step 1 |
| RF-02 (src/models.py unificado, espejo v2) | Step 2, 3 |
| RF-03 (modelo Claude) | Diferido a U4 (con TASK-005) |
| RNF-01 (sin credenciales en payload/código) | Step 2 (el modelo no admite email/url — extra="forbid") |
| RNF-08 (versiones pinned, sin latest) | Step 1, Step 4 |
| RNF-10 (reproducibilidad) | Step 1, Step 4 |
