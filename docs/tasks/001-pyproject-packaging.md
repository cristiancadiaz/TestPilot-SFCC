---
id: TASK-001
title: pyproject.toml con dependencias pinned + ruff/mypy
milestone: "M1: Packaging & Container Foundation"
priority: 1
estimate: 2
blockedBy: []
blocks: [TASK-002, TASK-003]
parent: null
---

## Summary
Crear `pyproject.toml` (PEP 621) con dependencias directas pinned y la configuración de `ruff`, `mypy` y `pytest`, para habilitar build reproducible (RNF-10) y supply chain segura (RNF-08).

## Scope
- **Incluye:** crear `pyproject.toml` en la raíz.
- **Reservado (no tocar):** `infra/`, `specs/`, `.github/workflows/` (rutas HITL).

## Deliverables
- `pyproject.toml` con:
  - `[project]`: `name`, `version = "0.1.0"`, `requires-python = ">=3.12"`.
  - Deps pinned: `fastapi`, `uvicorn[standard]`, `pydantic`, `anthropic`, `playwright`, `boto3`, `jsonschema`.
  - `[project.optional-dependencies].dev`: `pytest`, `pytest-asyncio`, `pytest-playwright`, `hypothesis`, `mypy`, `ruff`, `httpx`.
  - `[tool.ruff]`: `line-length = 100`, `target-version = "py312"`.
  - `[tool.mypy]`: `strict = true`, `python_version = "3.12"`.
  - `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `pythonpath = ["."]`, `asyncio_mode = "auto"`.

## Acceptance Criteria
- `pip install -e ".[dev]"` instala sin errores.
- `ruff check .` exit 0 (sin errores de configuración).
- `mypy src/` corre sin errores de configuración.
- Todas las versiones están pinned (sin `latest`, sin rangos abiertos) — RNF-08.

## Test Plan
- `pip install -e ".[dev]"` → exit 0.
- `ruff check .` → exit 0.
- `python -c "import tomllib,pathlib; tomllib.loads(pathlib.Path('pyproject.toml').read_text())"` → parsea sin error.

## Context
- `aidlc-docs/construction/plans/u0-code-generation-plan.md` (Step 1).
- `aidlc-docs/construction/u0/nfr-requirements/tech-stack-decisions.md`.
- `CLAUDE.md` § Hard Invariants (supply chain) · § Requires Human Confirmation (`pyproject.toml` es HITL).

## Definition of Ready
Cumple `docs/definition-of-ready.md`: scope acotado, AC medibles, sin dependencias bloqueantes. **Nota HITL:** `pyproject.toml` requiere confirmación humana antes de merge.
