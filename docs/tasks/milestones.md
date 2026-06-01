# Milestones — planning wave `u0-setup-base-implementation`

Unidad: **U0 — Setup Base**. Fuente: `aidlc-docs/construction/plans/u0-code-generation-plan.md`.
U0 es prerrequisito de todas las demás unidades (ver `build-sequence.md`).

## M1: Packaging & Container Foundation

**Objetivo:** dejar el proyecto empaquetable y contenerizable de forma reproducible
(deps pinned, ruff/mypy configurados, imagen Docker base Playwright).

- TASK-001 — `pyproject.toml` con deps pinned + ruff/mypy
- TASK-002 — `Dockerfile` + `.dockerignore`

**Exit criteria:** `pip install -e ".[dev]"` ok · `ruff check .` exit 0 · `docker build` completa.

## M2: Shared Models Unification

**Objetivo:** unificar `SyntheticUserConfig` y todos los modelos compartidos en
`src/models.py`, eliminar la duplicación en `translator.py` y `api/main.py`, y
verificar el Gate de U0.

- TASK-003 — `src/models.py` (modelos Pydantic unificados)
- TASK-004 — `tests/test_models.py`
- TASK-005 — Refactor `translator.py` + `api/main.py` → import de `src.models`
- TASK-006 — Verificación de Gate U0 + `code-summary.md`

**Exit criteria:** `mypy src/` exit 0 · `uv run pytest` exit 0 · tests existentes siguen pasando · Gate 1 de `build-sequence.md` verde.

## Dependencias (resumen)

```
TASK-001 ─┬─> TASK-002 ─────────────┐
          └─> TASK-003 ─┬─> TASK-004 ─┼─> TASK-006
                        └─> TASK-005 ─┘
```
