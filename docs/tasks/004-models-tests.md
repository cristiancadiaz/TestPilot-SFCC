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
Crear `tests/test_models.py` que valide la construcción y los invariantes de todos los modelos de `src/models.py`, alineado con el contrato `specs/` (RF-02).

## Scope
- **Incluye:** `tests/test_models.py`.
- **Reservado:** no modificar `src/models.py` (si falta algo, reportar a TASK-003).

## Deliverables
`tests/test_models.py` con (naming `test_should_..._when_...` o el del plan):

- `test_synthetic_user_config_valid` — instancia válida (con `flows[]`/`profiles[]`/`products[]`) pasa.
- `test_synthetic_user_config_rejects_production` — `environment_id="production"` → `ValidationError` (invariante: nunca producción).
- `test_synthetic_user_config_invalid_flow` — flow fuera de catálogo → `ValidationError`.
- `test_synthetic_user_config_invalid_profile` — profile fuera de catálogo → `ValidationError`.
- `test_synthetic_user_config_flows_bounds` — `flows` vacío y con >2 ítems → `ValidationError`; duplicados rechazados.
- `test_synthetic_user_config_profiles_bounds` — `profiles` vacío y con >3 ítems → `ValidationError`; duplicados rechazados.
- `test_synthetic_user_config_products_bounds` — `products` vacío y con >10 ítems → `ValidationError`; `search_term` < 2 chars → `ValidationError`.
- `test_run_options_screenshots_must_be_false` — `capture_intermediate_screenshots=True` → `ValidationError` (invariante de costo).
- `test_run_options_defaults` — `timeout_seconds == 180`; `Product.validate_variant == True`.
- `test_flow_result_orders_created_default` (== 0)
- `test_execution_report_orders_created_default` (== 0)
- `test_traffic_light_values` (GREEN/YELLOW/RED)
- `test_browser_profile_valid`
- `test_run_record_valid` (datetime timezone-aware)

## Acceptance Criteria
- `uv run pytest tests/test_models.py` pasa 100%.
- Cubre explícitamente: invariante 2 (catálogo cerrado de flows/profiles), nunca-producción, invariante de costo (screenshots) y los defaults de `orders_created`.

## Test Plan
- `uv run pytest tests/test_models.py -v` → todos verdes.

## Context
- `specs/synthetic-user-config.schema.json` — contrato (enums, bounds, unicidad, defaults).
- `src/models.py` (TASK-003).

## Definition of Ready
Depende de TASK-003. Cada constraint del schema (enum, min/max, unicidad, const) debe tener al menos un test de caso inválido.
