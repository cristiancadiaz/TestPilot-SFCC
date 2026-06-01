---
id: TASK-003
title: src/models.py — modelos Pydantic unificados
milestone: "M2: Shared Models Unification"
priority: 1
estimate: 3
blockedBy: [TASK-001]
blocks: [TASK-004, TASK-005]
parent: null
---

## Summary
Crear `src/models.py` como **único punto de definición** de `SyntheticUserConfig` y todos los modelos compartidos, resolviendo la duplicación heredada (RF-02).

## Scope
- **Incluye:** crear `src/models.py`.
- **Reservado:** no editar `translator.py` ni `api/main.py` todavía (eso es TASK-005); no tocar `specs/`.

## Deliverables
`src/models.py` con (en orden de dependencia):
1. `TrafficLight(str, Enum)`: GREEN, YELLOW, RED.
2. `SyntheticUserConfig`: validators de `testRunId` (UUID), `storefrontUrl` (http/https), `email` (**siempre `@testpilot.internal`**), `flow` (Literal del catálogo cerrado), `profile` (Literal), `timeout` (30000–180000).
3. `BrowserProfile`, `StepResult`, `FlowResult` (`orders_created: int = 0`), `ProfileResult`, `RunRecord`, `BaselineComparison`, `ExecutionReport` (`orders_created: int = 0`).

## Acceptance Criteria
- `mypy src/models.py` exit 0 (config strict).
- Todos los modelos se instancian desde tests.
- `flow`/`profile` solo aceptan valores del catálogo cerrado (invariante 2).
- email sin `@testpilot.internal` → `ValidationError` (invariante 1).
- `FlowResult().orders_created == 0` y `ExecutionReport(...).orders_created == 0`.

## Test Plan
Cubierto por TASK-004. Verificación local: `mypy src/models.py` + `python -c "from src.models import SyntheticUserConfig, ExecutionReport, TrafficLight"`.

## Context
- `aidlc-docs/construction/plans/u0-code-generation-plan.md` (Step 2).
- `aidlc-docs/construction/u0/functional-design/domain-entities.md` y `business-rules.md`.
- `specs/synthetic-user-config.schema.json` (contrato — solo lectura).
- `CLAUDE.md` § Hard Invariants 1, 2.

## Definition of Ready
Depende de TASK-001. Los validators deben reflejar exactamente el schema de `specs/` (sin redefinir el contrato). Catálogo de flows: `checkout_full`, `checkout_card_declined`.
