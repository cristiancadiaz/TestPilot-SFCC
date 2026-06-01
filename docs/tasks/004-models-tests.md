---
id: TASK-004
title: tests/test_models.py
milestone: "M2: Shared Models Unification"
priority: 2
estimate: 2
blockedBy: [TASK-003]
blocks: [TASK-006]
parent: null
---

## Summary
Crear `tests/test_models.py` que valide la construcción y los invariantes de todos los modelos de `src/models.py` (RF-02).

## Scope
- **Incluye:** `tests/test_models.py`.
- **Reservado:** no modificar `src/models.py` (si falta algo, reportar a TASK-003).

## Deliverables
`tests/test_models.py` con (naming `test_should_..._when_...` o el del plan):
- `test_synthetic_user_config_valid`
- `test_synthetic_user_config_email_validation` (email sin `@testpilot.internal` → falla)
- `test_synthetic_user_config_invalid_flow` (flow fuera de catálogo → `ValidationError`)
- `test_synthetic_user_config_invalid_profile`
- `test_synthetic_user_config_invalid_url`
- `test_synthetic_user_config_invalid_uuid`
- `test_flow_result_orders_created_default` (== 0)
- `test_execution_report_orders_created_default` (== 0)
- `test_traffic_light_values` (GREEN/YELLOW/RED)
- `test_browser_profile_valid`
- `test_run_record_valid` (datetime timezone-aware)

## Acceptance Criteria
- `uv run pytest tests/test_models.py` pasa 100%.
- Cubre explícitamente los invariantes 1 (email/orders) y 2 (catálogo cerrado).

## Test Plan
- `uv run pytest tests/test_models.py -v` → todos verdes.

## Context
- `aidlc-docs/construction/plans/u0-code-generation-plan.md` (Step 3).
- `src/models.py` (TASK-003).

## Definition of Ready
Depende de TASK-003. Cada validator de `SyntheticUserConfig` debe tener al menos un test de caso inválido.
