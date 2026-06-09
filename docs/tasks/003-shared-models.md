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

> 🔄 **Reconciliada a specs v2 (2026-06-03):** el contrato saltó a v2 (realineación de alcance — flows de recorrido + `full_journey` + `mode`). Esta task espeja **v2**. Delta para Linear (CHR-7): deliverables 4 y AC actualizados.

## Summary
Crear `src/models.py` como **único punto de definición** de `SyntheticUserConfig` y todos los modelos compartidos, espejando **exactamente** el contrato `specs/synthetic-user-config.schema.json` **v2** (RF-02).

## Scope
- **Incluye:** crear `src/models.py`.
- **Reservado:** no tocar `specs/` (es el contrato, solo lectura). No crear `translator.py` ni `api/main.py` (fuera del alcance greenfield de U0).

## Deliverables
`src/models.py` con (en orden de dependencia):

1. `TrafficLight(str, Enum)`: GREEN, YELLOW, RED.
2. `Product`: `search_term` (str, 2–128 chars), `validate_variant` (bool = True).
3. `RunOptions`: `timeout_seconds` (int, 30–600, default 180), `capture_intermediate_screenshots` (bool, **siempre False** — invariante de costo).
4. `SyntheticUserConfig` — **espeja el schema v2** (`additionalProperties: false`):
   - `schema_version`: `Literal["v2"] = "v2"`
   - `environment_id`: `Literal["sandbox", "development", "staging"]` (**production imposible** — invariante: nunca producción)
   - `flows`: `list[Literal["checkout_full", "checkout_card_declined", "search_and_filter", "browse_discounted_products", "pdp_validation", "cart_review", "full_journey"]]`, **1–6 ítems**, únicos (catálogo cerrado v2, invariante 2). Nota: `full_journey` es un **alias de composición** — el modelo lo acepta como valor del enum; su expansión a la secuencia de flows es responsabilidad del FlowCatalog (U5), NO de este modelo.
   - `mode`: `Literal["gate", "exploratory"] = "gate"` (RF-28 — exploratorio nunca entra al baseline, C11)
   - `profiles`: `list[Literal["mobile_co", "desktop_co", "desktop_ec"]]`, 1–3 ítems, únicos (catálogo cerrado)
   - `products`: `list[Product]`, 1–10 ítems
   - `options`: `RunOptions | None`
5. `BrowserProfile`, `StepResult`, `FlowResult` (`orders_created: int = 0`), `ProfileResult`, `RunRecord`, `BaselineComparison`, `ExecutionReport` (`test_run_id`, `mode` — requerido en report v2, `orders_created: int = 0`).

> **Nota de alcance v2:** los campos `audit` y `network_summary` del `execution_report.schema.json` v2 NO se modelan en U0 — los agregan U6/U7 (sus planes ya contemplan extender `src/models.py`). U0 modela el reporte mínimo viable de la ola 1 + el campo `mode` (requerido).

> **Nota sobre el invariante de email (zero contamination):** el contrato vigente **eliminó `shopper`/`email`** del payload (las credenciales se resuelven server-side desde Secrets Manager). Por tanto el invariante "email siempre `@testpilot.internal`" **NO se enforcea en este modelo** — se valida server-side donde se resuelve el shopper. `SyntheticUserConfig` **no lleva** `email`, `storefrontUrl`, `testRunId` ni `timeout` top-level (el `testRunId` se genera server-side y vive en `ExecutionReport.test_run_id`; el timeout vive en `options.timeout_seconds`).

## Acceptance Criteria
- `mypy src/models.py` exit 0 (config strict).
- Todos los modelos se instancian desde tests.
- `flows`/`profiles` solo aceptan valores del catálogo cerrado **v2** (invariante 2); fuera de catálogo → `ValidationError`. Los 4 flows de recorrido y `full_journey` son aceptados.
- `mode` acepta solo `gate`/`exploratory`, default `gate`; otro valor → `ValidationError`.
- `schema_version` solo acepta `"v2"`.
- `environment_id = "production"` → `ValidationError` (invariante: nunca producción).
- `capture_intermediate_screenshots = True` → `ValidationError` (invariante de costo).
- `flows` respeta **1–6 ítems** y unicidad; `profiles`/`products` respetan sus min/max del schema.
- `FlowResult().orders_created == 0` y `ExecutionReport(...).orders_created == 0`.
- Los 4 ejemplos embebidos en `specs/synthetic-user-config.schema.json` (v2) instancian `SyntheticUserConfig` sin error (incluye el ejemplo con `full_journey` + `mode`).

## Test Plan
Cubierto por TASK-004. Verificación local: `mypy src/models.py` + `python -c "from src.models import SyntheticUserConfig, ExecutionReport, TrafficLight"`.

## Context
- `specs/synthetic-user-config.schema.json` (**v2**) — **contrato y fuente de verdad** (solo lectura).
- `specs/execution_report.schema.json` (v2) — para `mode` requerido en el reporte (campos `audit`/`network_summary` quedan para U6/U7).
- `aidlc-docs/construction/u0/functional-design/domain-entities.md` y `business-rules.md`.
- `CLAUDE.md` § Hard Invariants 1 (zero contamination), 2 (catálogo cerrado v2), 3 (JSON Schema gate).
- `aidlc-docs/construction/plans/u0-code-generation-plan.md` — reconciliado a v2 el 2026-06-03.

## Definition of Ready
Depende de TASK-001. Los validators deben reflejar **exactamente** el schema v2 de `specs/` (sin redefinir el contrato). Catálogo de flows v2: `checkout_full`, `checkout_card_declined`, `search_and_filter`, `browse_discounted_products`, `pdp_validation`, `cart_review`, `full_journey`. Catálogo de profiles: `mobile_co`, `desktop_co`, `desktop_ec`.
