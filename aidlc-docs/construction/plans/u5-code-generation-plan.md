# U5 Journey Flows — Code Generation Plan (reconciled to wave-1 reality, 2026-06-08)

> ★ Ola 2, Sprint 4 (paralelo con U7/U8). Prereqs: U1 executor + U4 orchestrator +
> specs v2 — todos ✅. **Part 1 — Planning**; awaiting HITL approval before generation.
>
> ⚠️ **Protected path:** this unit creates files under `src/executor/flows/` — per
> CLAUDE.md these "run against staging/production storefronts" and need explicit human
> confirmation before editing. Generation proceeds only on approval.

## What U5 delivers

The 4 store-journey flows + the closed-catalog registry + `full_journey` composition,
so a user can validate a single module, a subset, or the whole store journey.

Stories: H6.1–H6.4 · RF-21, RF-22. Gate U5: generic dispatch (no if/else per flow) ·
`full_journey` has no flow file (D15) · no journey flow touches payment (static test) ·
composition tests green.

## Reconciliation with wave-1 (what already exists)

- **`FlowName` enum is already complete** in `src/models.py` (all 6: checkout_full,
  checkout_card_declined, search_and_filter, browse_discounted_products, pdp_validation,
  cart_review). Step 9 of the old plan is **done** — `mode`/`phase` also exist. U5 adds
  no enum values.
- **`FLOW_REGISTRY` currently lives in `src/executor/runner.py`** (2 entries). U5 moves
  the closed catalog to `flow_catalog.py` as the single source of truth (CLAUDE.md
  boundary); `runner.py` imports it (decision **D-U5-1**).
- **The U4 orchestrator currently rejects `full_journey` → 422** (`_resolve_flows`,
  wave-1 guard). U5 replaces that guard with `flow_catalog.expand_flows(...)` and routes
  `full_journey` to a composition run (decision **D-U5-2**) — this lifts the wave-1 422.
- Flow pattern (match U1): `async def run(page, config, env, run_id, profile_id) -> FlowResult`,
  selectors only from `SFCCSelectors`, waits via `wait_for_selector`/`expect` (never
  `time.sleep`), evidence per ADR-003 (fail+final always; finding/critical in audit mode).
- selectors.py groups today: `LOGIN_*`, `SEARCH_*`, `PDP_*`, `CART_*` (+ checkout/payment).

## Decisions (HITL — recommended defaults in **bold**)

- **D-U5-1 — registry home.** `flow_catalog.py` owns the closed catalog (registry +
  `critical_points` + `COMPOSITIONS` + `expand_flows`); `runner.py` imports it. Removes
  the duplicate 2-entry dict.
- **D-U5-2 — composition dispatch.** `full_journey` runs as a **chained composition in
  one shared browser context** per profile (`run_composition`), producing **one
  FlowResult per modular flow** (H6.3 AC4). Other flow sets run per-flow as today
  (`run_profile`). The orchestrator expands flows, then routes: composition vs per-flow.
- **D-U5-3 — selector fidelity (R2).** Journey flows are written against the documented
  SFRA selector contract and tested with a mocked `Page` (same as U1's checkout flows).
  Real-storefront validation needs R1/R2 resolution (live store + anti-bot IP) — out of
  scope here; selectors are documented in `selectors.py` and repaired when a store is wired.

## Steps

### Step 1 — `src/executor/flow_catalog.py` [x] (CREATE)
- `CLOSED_CATALOG`: dict `flow_name → FlowSpec(module run-coro, critical_points: list[str], preconditions)`.
- `COMPOSITIONS = {"full_journey": ["search_and_filter", "pdp_validation", "cart_review", "checkout_full"]}`.
- `expand_flows(flows: list[FlowSelection]) -> list[FlowName]`: expand `full_journey` to its
  sequence, dedupe preserving order, reject out-of-catalog (raise `ValueError`). `full_journey`
  is NEVER returned as a flow.
- `is_composition(flows) -> bool` / `composition_sequence(flows)` helpers for the orchestrator.

### Step 2 — extend `src/executor/selectors.py` [x] (MODIFY)
- New groups `PLP_*` (grid, category/price refinements, applied-refinement state) and
  `PROMOTIONS_*` (offers nav, struck original price, discounted price, discount badge).
  One comment per constant; `data-cmp-`/`data-testid` where SFRA exposes them.

### Step 3 — `src/executor/flows/search_and_filter.py` [x] (CREATE, protected)
Steps: `env_access_auth → search_from_header → plp_results_validation → apply_refinement →
grid_response_validation`. `setup()` no-op. Emits observed prices (for U6 collectors).

### Step 4 — `src/executor/flows/browse_discounted_products.py` [x] (CREATE, protected)
Steps: `env_access_auth → navigate_to_promotions → plp_discount_display_validation →
select_discounted_product → pdp_discount_consistency`. Discount inconsistency = finding
data, not a hard failure (H6.4 AC3). Emits PLP/PDP prices.

### Step 5 — `src/executor/flows/pdp_validation.py` [x] (CREATE, protected)
Steps: `env_access_auth → search_product → pdp_price_visible → pdp_variant_selector →
pdp_gallery_loads → pdp_add_to_cart_enabled`. `setup()` = product search.

### Step 6 — `src/executor/flows/cart_review.py` [x] (CREATE, protected)
Steps: `cart_product_present → cart_quantity_update → cart_subtotal_recalc →
cart_price_consistency`. `setup()` = search + add to cart, steps marked `phase="setup"`
(H6.2 AC3).

### Step 7 — `src/executor/runner.py` [x] (MODIFY)
- Import the registry from `flow_catalog` (drop the local dict).
- Add `run_composition(profile, flow_names, config, env, run_id) -> list[ProfileResult]`:
  one browser context, runs flows in sequence, skips intermediate `setup()`, a broken link
  → remaining flows `skipped` (H6.3 AC3). Returns one ProfileResult per flow.

### Step 8 — `src/executor/flows/__init__.py` [x] (MODIFY)
Export the 4 new flow modules.

### Step 9 — `src/api/services/run_orchestrator.py` [x] (MODIFY — U4 integration)
- Replace the wave-1 `_resolve_flows` guard with `flow_catalog.expand_flows(...)`
  (lifts the `full_journey` 422; out-of-catalog still → 422 `validation_failed`).
- Route: if `full_journey` requested → `run_composition` per profile; else `run_profile`
  per (profile, flow). Live tracker + baseline `save_run` per resulting FlowResult unchanged.

### Step 10 — `tests/test_flow_catalog.py` [x] (CREATE)
`expand_flows(["full_journey"])` == declared sequence; `["full_journey","cart_review"]`
dedupes; out-of-catalog raises; **static test:** no journey flow imports PAYMENT selectors
or contains payment steps (H6.1 AC2 — grep the modules).

### Step 11 — `tests/test_journey_flows.py` [x] (CREATE)
MagicMock `Page`: each flow returns a `FlowResult` with the expected steps; cart_review
`setup()` steps carry `phase="setup"`; browse_discounted emits structured prices; a failed
step → subsequent steps `skipped`.

### Step 12 — `tests/test_runner_composition.py` + `tests/test_api_full_journey.py` [x] (CREATE)
- Composition preserves context (same `Page` across flows); failure in link 2 → links 3–4
  `skipped`; generic dispatch works for all 6 flows with no if/else.
- API: `POST /v1/run` with `flows=["full_journey"]` now → 200 with one `profile_result`
  per expanded flow (was 422 in wave 1).

## Gate U5 (build-sequence) — CLOSED 2026-06-09
- [x] Generic dispatch — zero if/else per flow name (registry lookup)
- [x] `full_journey` has no flow file; expanded before the executor
- [x] No journey flow touches payment (static import/step test — `test_flow_catalog.py`)
- [x] Composition tests green (shared context, skip propagation — `test_runner_composition.py`)
- [x] `ruff` + `mypy --strict` exit 0; full `pytest` suite green (**196 passed**)

## Verification
```bash
uv run ruff check src/executor/ src/api/services/run_orchestrator.py tests/test_flow_catalog.py tests/test_journey_flows.py tests/test_runner_composition.py tests/test_api_full_journey.py
uv run mypy src
uv run pytest tests/test_flow_catalog.py tests/test_journey_flows.py tests/test_runner_composition.py tests/test_api_full_journey.py -v
uv run pytest    # full suite stays green
```
