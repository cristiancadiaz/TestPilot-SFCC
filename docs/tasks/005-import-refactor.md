---
id: TASK-005
title: Refactor translator.py + api/main.py para importar de src.models
milestone: "M2: Shared Models Unification"
priority: 2
estimate: 2
blockedBy: [TASK-003]
blocks: [TASK-006]
parent: null
---

> ⚠️ **DIFERIDA — fuera del alcance greenfield de U0.** Esta tarea asume que
> `src/agents/translator.py` y `src/api/main.py` ya existen con un `SyntheticUserConfig`
> duplicado, pero **ese scaffolding no existe** en el repo (ni en el workspace viejo).
> No hay nada que deduplicar todavía. La deduplicación pertenece a **cuando ese código
> exista** (unidad U4 / misión de API scaffolding). **NO está en el manifest de U0**
> (`task-package.yaml`) y no se publica en Linear como parte de esta ola.

## Summary
Eliminar las definiciones duplicadas de `SyntheticUserConfig` en `src/agents/translator.py` y `src/api/main.py`, importándola desde `src.models`, y actualizar el modelo Claude a una versión vigente (RF-02, RF-03).

## Scope
- **Incluye:** `src/agents/translator.py`, `src/api/main.py` (+ `src/agents/__init__.py` si cambia el import).
- **Reservado:** no cambiar la lógica funcional de los endpoints ni del traductor; no tocar `specs/`.

## Deliverables
- `translator.py`: constante `CLAUDE_MODEL = "claude-haiku-4-5-20251001"` (reemplaza el string hardcoded); eliminar la clase `SyntheticUserConfig` local; `from src.models import SyntheticUserConfig`.
- `api/main.py`: eliminar la clase `SyntheticUserConfig` local y sus validators/`model_config`; eliminar imports no usados; `from src.models import SyntheticUserConfig`; mantener `RunResponse`, `app` y el endpoint `run_test` sin cambios funcionales.

## Acceptance Criteria
- `mypy src/agents/translator.py` y `mypy src/api/main.py` exit 0.
- Los tests existentes `tests/test_translator.py` y `tests/test_schemas.py` siguen pasando.
- No queda ninguna definición duplicada de `SyntheticUserConfig` fuera de `src/models.py`.

## Test Plan
- `uv run pytest tests/test_translator.py tests/test_schemas.py -v` → verdes.
- `grep -rn "class SyntheticUserConfig" src/` → solo aparece en `src/models.py`.

## Context
- `aidlc-docs/construction/plans/u0-code-generation-plan.md` (Steps 4, 5).
- `CLAUDE.md` § Patterns (llamadas Claude API solo vía `src/agents/`).

## Definition of Ready
Depende de TASK-003. Cambio brownfield: preservar comportamiento; cualquier cambio de firma pública del endpoint sería breaking y queda fuera de scope.
