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

> 🔄 **Reconciliada a specs v2 (2026-06-03):** tests nuevos para `mode`, flows de recorrido, `full_journey`, bounds 1–6 y ejemplos reales del schema. Delta para Linear (CHR-8).

## Summary
Crear `tests/test_models.py` que valide la construcción y los invariantes de todos los modelos de `src/models.py`, alineado con el contrato `specs/` **v2** (RF-02).

## Scope
- **Incluye:** `tests/test_models.py`.
- **Reservado:** no modificar `src/models.py` (si falta algo, reportar a TASK-003).

## Deliverables
`tests/test_models.py` con (naming `test_should_..._when_...` o el del plan):

- `test_synthetic_user_config_valid` — instancia válida (con `flows[]`/`profiles[]`/`products[]`) pasa.
- `test_synthetic_user_config_schema_version_v2` — default `"v2"`; `"v1"` → `ValidationError`.
- `test_synthetic_user_config_rejects_production` — `environment_id="production"` → `ValidationError` (invariante: nunca producción).
- `test_synthetic_user_config_invalid_flow` — flow fuera de catálogo → `ValidationError`.
- `test_synthetic_user_config_accepts_journey_flows` — los 4 flows de recorrido + `full_journey` aceptados (catálogo v2).
- `test_synthetic_user_config_mode` — default `"gate"`; `"exploratory"` aceptado; otro valor → `ValidationError`.
- `test_synthetic_user_config_invalid_profile` — profile fuera de catálogo → `ValidationError`.
- `test_synthetic_user_config_flows_bounds` — `flows` vacío y con **>6 ítems** → `ValidationError`; duplicados rechazados.
- `test_synthetic_user_config_profiles_bounds` — `profiles` vacío y con >3 ítems → `ValidationError`; duplicados rechazados.
- `test_schema_examples_instantiate` — los 4 ejemplos embebidos en `specs/synthetic-user-config.schema.json` instancian sin error (round-trip contra el contrato real).
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
- Cubre explícitamente: invariante 2 (catálogo cerrado **v2**, incl. recorrido + `full_journey`), `mode` gate/exploratory, nunca-producción, invariante de costo (screenshots), bounds 1–6 de flows, defaults de `orders_created`, y los ejemplos reales del schema.

## Test Plan
- `uv run pytest tests/test_models.py -v` → todos verdes.

## Context
- `specs/synthetic-user-config.schema.json` (**v2**) — contrato (enums, bounds, unicidad, defaults, `mode`).
- `src/models.py` (TASK-003).

## Definition of Ready
Depende de TASK-003. Cada constraint del schema (enum, min/max, unicidad, const) debe tener al menos un test de caso inválido.
