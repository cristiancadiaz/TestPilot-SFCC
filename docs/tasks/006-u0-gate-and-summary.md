---
id: TASK-006
title: Verificación de Gate U0 + code-summary.md
milestone: "M2: Shared Models Unification"
priority: 3
estimate: 1
blockedBy: [TASK-002, TASK-004, TASK-005]
parent: null
blocks: []
---

## Summary
Ejecutar el Gate 1 de `build-sequence.md` para U0 y registrar el resumen de la unidad en `aidlc-docs/construction/u0/code/code-summary.md` (Step 8).

## Scope
- **Incluye:** ejecutar los gates y crear/actualizar `aidlc-docs/construction/u0/code/code-summary.md`.
- **Reservado:** no implementar U1–U4.

## Deliverables
- Evidencia de los 4 gates ejecutados (ver Test Plan).
- `aidlc-docs/construction/u0/code/code-summary.md` con: archivos creados/modificados, versiones usadas, decisiones relevantes, y el mapa RF/RNF → archivo/test.

## Acceptance Criteria
- `ruff check .` exit 0.
- `mypy src/` exit 0.
- `uv run pytest` exit 0 (incluye `test_models.py`, `test_schemas.py`, `test_translator.py`).
- `docker build -t testpilot-sfcc:local .` completa.
- Gate 1 de `build-sequence.md` queda con todos los checkboxes marcados.

## Test Plan
```bash
ruff check .
mypy src/
uv run pytest
docker build -t testpilot-sfcc:local .
```
Los 4 deben terminar en exit 0.

## Context
- `aidlc-docs/construction/plans/build-sequence.md` (Gate 1 — Tras U0).
- `aidlc-docs/construction/plans/u0-code-generation-plan.md` (Step 8 + verificación final).

## Definition of Ready
Depende de TASK-002, TASK-004 y TASK-005 (toda la unidad implementada). Es la tarea de cierre/gate de U0.
