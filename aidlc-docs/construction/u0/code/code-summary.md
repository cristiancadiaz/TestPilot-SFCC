# Code Summary — U0 Setup Base

> Cierre de unidad (TASK-006, Gate 1 de `build-sequence.md`). Reescrito 2026-06-06
> para reflejar el **alcance greenfield realineado**: U0 entrega modelos +
> packaging + contenedor. La deduplicación de `translator.py`/`api/main.py`
> (TASK-005) quedó **DIFERIDA** — ese scaffolding no existe en el repo; pertenece
> a U4. Ver `docs/tasks/005-import-refactor.md`.

## Alcance real entregado

U0 son las fundaciones compartidas de las que dependen TODAS las demás unidades:
el contrato de datos en Python (espejo de `specs/` v2), el packaging reproducible
y la imagen de contenedor. No incluye executor, API, baseline ni reporter.

## Archivos creados

| Archivo | Tarea | Descripción |
|---------|-------|-------------|
| `pyproject.toml` | TASK-001 | Build system, dependencias pinned, config de ruff + mypy strict + pytest |
| `uv.lock` | TASK-001 | Lockfile reproducible (uv) |
| `Dockerfile` | TASK-002 | Imagen base `mcr.microsoft.com/playwright/python:v1.48.0-jammy`, usuario `pwuser`, `EXPOSE 8000` |
| `.dockerignore` | TASK-002 | Excluye `.env`, `.git`, `aidlc-docs/`, `tests/`, `__pycache__`, material de curso |
| `src/__init__.py` | TASK-003 | Docstring de paquete |
| `src/models.py` | TASK-003 | Modelos Pydantic unificados — única fuente de verdad, espejo de `specs/` v2 |
| `tests/__init__.py` | TASK-004 | Marca el paquete de tests |
| `tests/test_models.py` | TASK-004 | 20 tests de validación de modelos contra specs v2 |

## Archivos NO modificados (TASK-005 diferida)

`src/agents/translator.py` y `src/api/main.py` **no existen** en el repo realineado.
La tarea original asumía deduplicar un `SyntheticUserConfig` duplicado en ellos; no
hay nada que deduplicar todavía. Se materializa en U4 (API scaffolding). Esta tarea
no está en el manifest de U0 (`task-package.yaml`).

## Modelos en `src/models.py`

Catálogos cerrados (espejo exacto de specs v2): `FlowSelection` (7 — incluye el alias
`full_journey`), `FlowName` (6 — nunca el alias; el reporte muestra la composición
expandida), `ProfileId`, `Mode` (gate|exploratory), `AuditDimension` (6),
`EnvironmentId` (sin `production` por construcción).

Request: `Product`, `RunOptions` (con `capture_intermediate_screenshots: Literal[False]`
— invariante de costo ADR-003), `SyntheticUserConfig` (`extra="forbid"`, uniqueItems).

Response: `BrowserProfile`, `StepResult` (con `screenshot_state` fail|final|finding|critical
y `finding_dimension` — política de evidencia ADR-003), `FlowResult`, `ProfileResult`,
`BaselineComparison`, `RunRecord`, `ExecutionReport`.

Invariante cero-contaminación: `orders_created` modelado con `Field(default=0, exclude=True)`
— accesible como atributo interno, nunca publicado en el contrato JSON.

Alcance de modelos: los objetos `audit` y `network_summary` del reporte v2 se difieren a
U6/U7. U0 modela el reporte mínimo viable de ola 1 + el campo `mode`. Credenciales
(env/shopper) se resuelven server-side (Secrets Manager) y se modelan en U4.

## Versiones clave fijadas

| Dependencia | Versión |
|-------------|---------|
| Python | >=3.12 |
| fastapi | 0.136.3 _(bump de seguridad 2026-06-06)_ |
| starlette | 1.2.1 _(pin directo — bump de seguridad 2026-06-06)_ |
| pydantic | 2.9.2 |
| anthropic | 0.39.0 |
| playwright | 1.48.0 |
| pytest | 9.0.3 _(bump de seguridad 2026-06-06)_ |
| pytest-asyncio | 1.4.0 |
| pytest-playwright | 0.8.0 |
| Imagen Docker base | `mcr.microsoft.com/playwright/python:v1.48.0-jammy` |

## Decisiones relevantes

- `src/models.py` es la única fuente de verdad de los modelos; espeja `specs/` v2
  (el contrato JSON sigue siendo la autoridad — HITL, breaking-change-sensitive).
- `run_id` (no `test_run_id`): el contrato publicado usa `run_id`; el schema gana
  sobre el texto de la tarea.
- `FlowSelection` vs `FlowName` separados: el request acepta el alias `full_journey`;
  el resultado nunca lo contiene (composición ya expandida por FlowCatalog — H6.3 AC4).
- `orders_created` excluido de la serialización pero presente como atributo (BR-U3-01).
- Dockerfile usa `pwuser` (no-root, incluido en la imagen base de Playwright).

## Gate 1 — Resultados (build-sequence.md)

Ejecutado 2026-06-06:

| Check | Comando | Resultado |
|-------|---------|-----------|
| Lint | `ruff check .` | ✅ exit 0 — All checks passed! |
| Tipos | `mypy src/` (strict) | ✅ exit 0 — no issues in 2 source files |
| Tests | `uv run pytest` | ✅ 20 passed |
| Contenedor | `docker build -t testpilot-sfcc:local .` | ✅ exit 0 — imagen 985 MB |
| Vulns | `uv run pip-audit` | ✅ No known vulnerabilities found (tras el bump — ver abajo) |
| API 422 | imagen responde `/v1/run` con 422 | N/A en U0 — no hay API todavía (U4) |

### Bump de seguridad `pip-audit` (HITL aprobado 2026-06-06)

El run inicial de TASK-006 reportó 4 vulnerabilidades en dependencias transitivas.
Con autorización HITL se resolvieron bumpeando a las versiones seguras (re-pin exacto
para preservar RNF-08 "todo pinneado"); `pip-audit` quedó limpio:

| Paquete | Antes | Después | CVE resuelta |
|---------|-------|---------|--------------|
| starlette | 0.38.6 | **1.2.1** (pin directo) | GHSA-f96h-pmfr-66vw + GHSA-2c2j-9gv5-cj73 + PYSEC-2026-161 |
| fastapi | 0.115.0 | **0.136.3** | (necesario para admitir starlette ≥1.0) |
| pytest | 8.3.3 | **9.0.3** | GHSA-6w46-j5rx-g56g (dev) |
| pytest-asyncio | 0.24.0 | **1.4.0** | (compat con pytest 9) |
| pytest-playwright | 0.5.2 | **0.8.0** | (compat con pytest 9) |

`starlette` se agregó como **dependencia directa pinneada** (antes era sólo transitiva
vía fastapi) para controlar la versión de seguridad de forma explícita. Tras el bump,
los 5 gates vuelven a verde (ruff/mypy/pytest 20/docker build/pip-audit). Efecto
colateral resuelto: desaparece el warning `asyncio_default_fixture_loop_scope` de
pytest-asyncio 0.24 (pytest-asyncio 1.x lo maneja).

## Mapa RF/RNF → archivo/test

| Requisito | Implementación | Test |
|-----------|---------------|------|
| Catálogo cerrado de flows (C2, inv. #2) | `FlowSelection`/`FlowName` en `models.py` | `tests/test_models.py` (rechazo de flow fuera de catálogo) |
| JSON Schema gate (C12, inv. #3) | `SyntheticUserConfig` con `extra="forbid"` | `tests/test_models.py` (extra fields, uniqueItems, bounds) |
| Cero contaminación (inv. #1) | `orders_created` exclude=True | `tests/test_models.py` (no aparece en `model_dump`) |
| Evidencia findings-driven (ADR-003, RF-26) | `screenshot_state`/`finding_dimension` en `StepResult` | `tests/test_models.py` |
| Invariante de costo screenshots (ADR-003) | `capture_intermediate_screenshots: Literal[False]` | `tests/test_models.py` |
| Modo gate vs exploratory (C11) | `Mode` en config + reporte | `tests/test_models.py` |
| Packaging reproducible | `pyproject.toml` + `uv.lock` | Gate 1 (pip install / docker build) |
| Contenedor reproducible | `Dockerfile` + `.dockerignore` | Gate 1 (docker build exit 0) |
