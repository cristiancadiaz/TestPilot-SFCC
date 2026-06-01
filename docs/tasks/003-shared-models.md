---
id: TASK-003
title: src/models.py — modelos Pydantic unificados
milestone: "M2: Shared Models Unification"
priority: 1
estimate: 3
blockedBy: [TASK-001]
blocks: [TASK-004]
parent: null
---

## Summary
Crear `src/models.py` como **único punto de definición** de `SyntheticUserConfig` y todos los modelos compartidos, espejando **exactamente** el contrato `specs/synthetic-user-config.schema.json` (RF-02).

## Scope
- **Incluye:** crear `src/models.py`.
- **Reservado:** no tocar `specs/` (es el contrato, solo lectura). No crear `translator.py` ni `api/main.py` (fuera del alcance greenfield de U0).

## Deliverables
`src/models.py` con (en orden de dependencia):

1. `TrafficLight(str, Enum)`: GREEN, YELLOW, RED.
2. `Product`: `search_term` (str, 2–128 chars), `validate_variant` (bool = True).
3. `RunOptions`: `timeout_seconds` (int, 30–600, default 180), `capture_intermediate_screenshots` (bool, **siempre False** — invariante de costo).
4. `SyntheticUserConfig` — **espeja el schema** (`additionalProperties: false`):
   - `schema_version`: `Literal["v1"] = "v1"`
   - `environment_id`: `Literal["sandbox", "development", "staging"]` (**production imposible** — invariante: nunca producción)
   - `flows`: `list[Literal["checkout_full", "checkout_card_declined"]]`, 1–2 ítems, únicos (catálogo cerrado, invariante 2)
   - `profiles`: `list[Literal["mobile_co", "desktop_co", "desktop_ec"]]`, 1–3 ítems, únicos (catálogo cerrado)
   - `products`: `list[Product]`, 1–10 ítems
   - `options`: `RunOptions | None`
5. `BrowserProfile`, `StepResult`, `FlowResult` (`orders_created: int = 0`), `ProfileResult`, `RunRecord`, `BaselineComparison`, `ExecutionReport` (`test_run_id`, `orders_created: int = 0`).

> **Nota sobre el invariante de email (zero contamination):** el contrato vigente **eliminó `shopper`/`email`** del payload (las credenciales se resuelven server-side desde Secrets Manager). Por tanto el invariante "email siempre `@testpilot.internal`" **NO se enforcea en este modelo** — se valida server-side donde se resuelve el shopper. `SyntheticUserConfig` **no lleva** `email`, `storefrontUrl`, `testRunId` ni `timeout` top-level (el `testRunId` se genera server-side y vive en `ExecutionReport.test_run_id`; el timeout vive en `options.timeout_seconds`).

## Acceptance Criteria
- `mypy src/models.py` exit 0 (config strict).
- Todos los modelos se instancian desde tests.
- `flows`/`profiles` solo aceptan valores del catálogo cerrado (invariante 2); fuera de catálogo → `ValidationError`.
- `environment_id = "production"` → `ValidationError` (invariante: nunca producción).
- `capture_intermediate_screenshots = True` → `ValidationError` (invariante de costo).
- `flows`/`profiles`/`products` respetan min/max y unicidad declarados en el schema.
- `FlowResult().orders_created == 0` y `ExecutionReport(...).orders_created == 0`.

## Test Plan
Cubierto por TASK-004. Verificación local: `mypy src/models.py` + `python -c "from src.models import SyntheticUserConfig, ExecutionReport, TrafficLight"`.

## Context
- `specs/synthetic-user-config.schema.json` — **contrato y fuente de verdad** (solo lectura).
- `aidlc-docs/construction/u0/functional-design/domain-entities.md` y `business-rules.md`.
- `CLAUDE.md` § Hard Invariants 1 (zero contamination), 2 (catálogo cerrado), 3 (JSON Schema gate).
- ⚠️ `aidlc-docs/construction/plans/u0-code-generation-plan.md` (Step 2) describe el modelo **viejo** (pre-breaking-change v1.1); este task espeja el schema **vigente**. El plan debe reconciliarse aparte.

## Definition of Ready
Depende de TASK-001. Los validators deben reflejar **exactamente** el schema de `specs/` (sin redefinir el contrato). Catálogo de flows: `checkout_full`, `checkout_card_declined`. Catálogo de profiles: `mobile_co`, `desktop_co`, `desktop_ec`.
