# Business Logic Model — U0 Setup Base (actualizado 2026-05-24)

## Propósito desde la perspectiva del producto

U0 es la **deuda técnica habilitadora**: sin ella, ninguna unidad nueva puede compilar consistentemente ni desplegarse de forma reproducible. **Cambio mayor vs versión anterior:** ahora también materializa el contrato de datos para el nuevo modelo de ambientes (`EnvironmentConfig`) y credenciales duales (env_access + shopper).

**Outcomes de negocio:**
1. **Reproducibilidad del build** — versiones pinned, imagen Docker tagged → el reporte del miércoles usa el mismo binario que el del lunes.
2. **Supply chain segura** — dependencias auditadas, sin `:latest`, usuario no-root.
3. **Contrato de datos único** — todos los modelos Pydantic en `src/models.py`. Cambios al contrato son visibles en un diff de un archivo.
4. **Soporte al nuevo modelo de ambientes** — `EnvironmentConfig`, `EnvironmentAccessCredentials`, `ShopperCredentials`, `ResolvedEnvironment` viven aquí desde día 1.

---

## Componentes de U0

```
src/models.py            ← TODOS los modelos Pydantic compartidos
src/agents/translator.py ← actualización: modelo Claude + import desde src/models
src/api/main.py          ← actualización: eliminar definiciones locales, importar de src/models
pyproject.toml           ← dependencias pinned, ruff, mypy, pytest config
Dockerfile               ← multi-stage (Node builder + Python runtime con Playwright)
.dockerignore            ← excluir .env, .git, aidlc-docs, __pycache__
```

---

## Flujo: definición y consumo de modelos

```
┌───────────────────────────────────────────────────────────────┐
│  src/models.py — fuente única de verdad                       │
│                                                               │
│  EnvironmentConfig, EnvironmentAccessCredentials,             │
│  ShopperCredentials, ResolvedEnvironment,                     │
│  SyntheticUserConfig, ExecutionReport, RunRecord,             │
│  RunStatus, BrowserProfile, StepResult, FlowResult,           │
│  ProfileResult, BaselineComparison, TrafficLight              │
└────────────┬──────────────────────────────────────────────────┘
             │ import
             ▼
   ┌─────────┴────────┬────────┬────────┬────────┬────────┐
   │                  │        │        │        │        │
src/agents/   src/executor/  src/baseline/  src/reporter/  src/api/
translator    runner+flows   baseline_mgr   report_gen     main
```

**Principio:** ningún módulo redefine modelos. Si necesita uno nuevo, lo agrega a `src/models.py`.

---

## Lógica de actualización de `translator.py`

Cambios respecto a versión actual:

```python
# ANTES
CLAUDE_MODEL = "claude-3-haiku-20240307"  # deprecated

class SyntheticUserConfig(BaseModel):  # definición local duplicada
    storefront_url: str
    email: str
    password: str
    ...

# DESPUÉS
from src.models import SyntheticUserConfig  # single source of truth

CLAUDE_MODEL = "claude-haiku-4-5-20251001"  # current per memoria del proyecto
```

**Comportamiento:** el translator sigue produciendo `SyntheticUserConfig` con la nueva forma (sin credenciales, con `environment_id`). El prompt al LLM se actualiza para enseñarle el catálogo cerrado y a inferir `environment_id` del NL ("en staging…", "para development…").

---

## Lógica de actualización de `api/main.py`

```python
# ANTES
class SyntheticUserConfig(BaseModel):  # local
    ...

@app.post("/v1/run")
async def run(config: SyntheticUserConfig) -> dict:
    return {"status": "queued"}

# DESPUÉS (parte mínima en U0 — la expansión real es U4)
from src.models import SyntheticUserConfig, ExecutionReport

@app.post("/v1/run")
async def run(config: SyntheticUserConfig) -> dict:
    return {"status": "queued", "run_id": "stub"}  # U4 lo expandirá
```

En U0 solo se hace la limpieza de duplicados. La integración real con executor/baseline/reporter es responsabilidad de U4.

---

## Lógica de `pyproject.toml`

```toml
[project]
name = "testpilot-sfcc"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi==0.115.0",
    "uvicorn[standard]==0.30.6",
    "pydantic==2.9.2",
    "pydantic[email]==2.9.2",          # EmailStr
    "playwright==1.48.0",
    "anthropic==0.39.0",
    "boto3==1.35.49",                  # Secrets Manager + DynamoDB + S3
    "jsonschema==4.23.0",
    "python-json-logger==2.0.7",       # structured logging
]

[project.optional-dependencies]
dev = [
    "pytest==8.3.3",
    "pytest-asyncio==0.24.0",
    "hypothesis==6.115.3",             # PBT
    "ruff==0.7.1",
    "mypy==1.13.0",
    "pip-audit==2.7.3",                # SECURITY-08
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "S"]  # S = bandit-style security
ignore = ["S101"]  # assert OK in our codebase (used for invariants)

[tool.mypy]
strict = true
python_version = "3.12"

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**Cambios vs versión anterior:**
- `boto3` agregado (Secrets Manager, DynamoDB, S3 — necesarios desde U0 porque `EnvironmentConfig` se persiste).
- `pip-audit` agregado para SECURITY-08.
- Versiones de `playwright`, `pydantic`, `fastapi` confirmadas como las del proyecto.

---

## Lógica del Dockerfile (versión multi-stage)

Detalle completo en `infrastructure-design/infrastructure-design.md`. Resumen:

- **Stage 1 (dashboard-builder):** Node 20 alpine → build de MD0 (Vite produce `dist/`).
- **Stage 2 (runtime):** imagen Playwright Python oficial → instala dependencias pip → copia `src/`, `specs/`, `dist/` → user no-root → expone 8000.

**Por qué multi-stage:** evita incluir Node en la imagen de producción (~50 MB menos), y permite que tests del backend corran sin necesidad de hacer build del dashboard.

---

## Tests que U0 debe garantizar pasen

- `tests/test_models.py` (NUEVO) — instanciar cada modelo Pydantic con datos válidos e inválidos.
- `tests/test_schemas.py` (EXISTENTE) — actualizar para que `SyntheticUserConfig` Pydantic conserve el contrato del JSON Schema migrado a la nueva forma.
- `tests/test_translator.py` (EXISTENTE) — actualizar mocks para esperar la nueva forma de `SyntheticUserConfig`.
- `tests/test_models_pbt.py` (NUEVO — PBT-08): round-trip `SyntheticUserConfig.model_dump() → model_validate()` debe ser identidad.

---

## Criterio de completitud (Definition of Done)

- [ ] `pyproject.toml` instalable con `pip install -e ".[dev]"` sin errores.
- [ ] `ruff check src/` sin warnings.
- [ ] `mypy src/` sin errores.
- [ ] `pytest tests/` todos pasan (existentes + nuevos).
- [ ] `pip-audit` sin vulnerabilidades HIGH/CRITICAL.
- [ ] `docker build .` produce imagen sin errores.
- [ ] Imagen producida ejecuta `uvicorn` correctamente y `curl localhost:8000/v1/run -X POST -d '{}'` retorna 422 (validation) sin crashear.
- [ ] `src/dashboard/dist/` se construye y se incluye en la imagen.
