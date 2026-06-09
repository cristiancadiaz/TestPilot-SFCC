# U8 NL Window + Operation Modes — Code Generation Plan (reconciled 2026-06-09)

> ★ Ola 2 (paralelo con U7). Prereqs: U4 API ✅ · MD0 dashboard ✅ · `specs/`
> `translate-request-response.schema.json` ✅ · baseline gate-only (C11) ✅ · FlowCatalog (U5) ✅.
> **Part 1 — Planning**; awaiting HITL approval before generation.

## What U8 delivers
The NL entry path: a Claude-backed translator (NL → validated, user-confirmed
`SyntheticUserConfig` + Spanish preview), the `POST /v1/translate` endpoint (strict
schema+catalog gate, prompt-injection hardened), the dashboard NL window, and the
operation-mode semantics (gate vs exploratory) end to end. **The NL never reaches the
executor (C12); exploratory runs never touch the baseline (C11).**

Stories: H9.1, H9.2, H9.3 · RF-27, RF-28. Restricciones: C12 · C11 · validación P3
estricta (schema + catálogo) · RT1 prompt-injection 100% bloqueado (Q8=0) · NL ≤2000 (RNF-05).

## Reconciliation with current reality (BIG divergences from the 2026-06-03 plan)
- **`src/agents/` does NOT exist.** The old plan said "promote the translator to a main
  component" assuming U0 created it — it didn't (U0 TASK-005 was deferred *to here*). U8
  must **CREATE `src/agents/translator.py` from scratch** (decision **D-U8-1**). TASK-005
  (translator/api model dedup) lands in U8.
- **There is no `src/api/main.py`.** U4 built `app.py` (factory) + `routers/`. The
  translate endpoint becomes **`src/api/routers/translate.py`** wired into `app.py`
  (decision **D-U8-2**), not a main.py edit.
- **`SyntheticUserConfig.mode` ALREADY EXISTS** (`models.py:128`, default `"gate"`). Step 1's
  mode work is done — only `TranslateRequest`/`TranslateResponse` models remain.
- **The baseline gate-only guard is ALREADY implemented** (C11 — `baseline_manager.py`:
  "exploratory runs are silently dropped"). Original Step 5 is essentially done; U8 only
  adds the PBT that proves p95 excludes exploratory runs.
- **`GET /v1/runs/latest` gate-only ALREADY EXISTS** (U4 Phase B). Original Step 4's
  latest-gate semantics are done; U8 confirms mode propagation (also already wired via U4/U5).
- **The dashboard lives at the repo root** (Vite/React/TS: `index.html`, `eslint.config.js`,
  `dist/` …), **not `src/dashboard/`**. The NL window is built in that app (decision **D-U8-6**).
- **The daily cap (10 runs/day, invariant #7) is NOT implemented anywhere.** New work
  (decision **D-U8-5**).

## Decisions (HITL — recommended defaults in **bold**)
- **D-U8-1 — create the translator.** New `src/agents/__init__.py` + `translator.py`.
  Claude API via the Anthropic SDK behind an injectable client Protocol + an in-memory
  fake (same pattern as U4's AWS fakes — tests NEVER call the real API). All Claude calls
  live here (boundary). TASK-005 dedup resolves here.
- **D-U8-2 — endpoint as a router.** `routers/translate.py` (X-API-Key auth, reuses the
  U4 security/middleware/error taxonomy) wired in `app.py`; the app factory gains a
  `translator` dependency. NOT a `main.py`.
- **D-U8-3 — post-translation gate reuses the closed catalog.** The endpoint validates the
  proposed config against `specs/` v2 (jsonschema) AND `flow_catalog.expand_flows` (closed
  catalog) BEFORE responding (P3). Out-of-catalog / injection → 422 `instruction_rejected`
  + logged attempt (RT1). The endpoint NEVER launches a browser (asserted).
- **D-U8-4 — baseline mode filter already satisfied.** Reuse the existing C11 guard; U8
  adds only the confirming PBT (no baseline_manager change unless the PBT exposes a gap).
- **D-U8-5 — daily cap (invariant #7).** Lightweight guard counting gate+exploratory runs
  per day (via RunReportStore/history) → `429 rate_limited` taxonomy row; full enforcement
  belongs to infra (Step Functions). **Recommend implementing the in-app guard now**; flag
  if you'd rather defer entirely to infra.
- **D-U8-6 — NL window in the root dashboard.** NL textarea as the primary path in NewRun;
  "Traducir" → preview (explanation + readable config) → "Confirmar y lanzar" → POST /v1/run;
  JSON editor demoted to an advanced toggle; gate/exploratory selector; exploratory runs
  visually flagged in history/detail.
- **Note — D-NL gates (Q1≥90%, Q2=100%) are an operational pre-launch eval**, not code
  (dataset evaluation). RT1 (Q8=0) IS in-scope as `test_prompt_injection.py`.

## Steps

### Step 1 — `src/models.py` [ ] (MODIFY)
Add `TranslateRequest` (instruction 2..2000) + `TranslateResponse` (status ok|ambiguous,
proposed_config, explanation, clarification_question) mirroring the schema. (mode already exists.)

### Step 2 — `src/agents/__init__.py` + `src/agents/translator.py` [x] (CREATE — D-U8-1)
Translator: prompt with the v2 closed catalog (6 flows + full_journey) + scope mapping
("revisa solo el carrito" → cart_review; "toda la tienda" → full_journey, RF-22 AC6);
ambiguity → `status="ambiguous"` + clarification question (NEVER guess, P3); Spanish
`explanation`; hardened system instructions + post-validation (prompt-injection defense).
Anthropic client behind a Protocol + in-memory fake.

### Step 3 — `src/api/routers/translate.py` + wire in `app.py` [x] (CREATE/MODIFY — D-U8-2/3)
`POST /v1/translate`: X-API-Key; validate `instruction` ≤2000; call translator; validate
proposed config vs schema v2 + `flow_catalog` BEFORE responding (P3); out-of-catalog /
injection → 422 `instruction_rejected` + log (RT1). NEVER runs anything.

### Step 4 — daily cap guard [x] (CREATE — D-U8-5)
In the orchestrator/deps: count today's runs (gate+exploratory) → `429 rate_limited` when
≥10 (invariant #7). New error-taxonomy row. (Mode propagation + latest-gate already done.)

### Step 5 — baseline mode PBT [ ] (CREATE — D-U8-4)
PBT confirming p95 never includes exploratory runs (the C11 guard already enforces this;
this locks it in). No baseline_manager change expected.

### Step 6 — dashboard NL window [ ] (MODIFY — D-U8-6)
Root Vite/React app: NL textarea primary in NewRun → "Traducir" → preview → "Confirmar y
lanzar" → POST /v1/run; JSON editor as advanced toggle; gate/exploratory selector; explore
runs flagged in history/detail. vitest + tsc strict + eslint green.

### Step 7 — `tests/test_translate_endpoint.py` [x] (CREATE)
Claude mocked: valid instruction → ok + config validates vs schema v2 + explanation;
ambiguous → ambiguous + clarification_question; >2000 → 422; no API key → 401; endpoint
NEVER launches the browser (assert executor not invoked).

### Step 8 — `tests/test_prompt_injection.py` [x] (CREATE)
RT1 suite (PRD §11.4, 5 scenarios: ignore-rules, out-of-catalog flow, malicious flow,
leak env vars, jailbreak prefix) → 100% rejected with 422 + log. **Gate Q8=0, blocking.**

### Step 9 — `tests/test_modes.py` + `tests/test_executor_no_translator_import.py` [x] (CREATE)
Modes: exploratory run absent from p95 (PBT mixed modes); `latest` for gate ignores
exploratory; exploratory report carries `mode="exploratory"`; daily cap sums both modes.
**C12 static test:** `src/executor/` has no import of `src/agents` (grep).

## Gate U8 (build-sequence)
- [ ] RT1 suite 100% blocked (Q8=0) — **blocking before exposing the NL window**
- [ ] Executor has no translator import (C12 static grep)
- [ ] Exploratory runs out of baseline AND latest-gate (C11)
- [ ] NL ≤2000 enforced; injection → 422 instruction_rejected + log
- [ ] `ruff` + `mypy --strict` exit 0; dashboard tsc+vitest+eslint green; full `pytest` green
- [ ] (Operational, post-code) D-NL: Q1≥90%, Q2=100% on the D-NL dataset

## Verification
```bash
uv run ruff check src/agents/ src/api/ tests/test_translate_endpoint.py tests/test_prompt_injection.py tests/test_modes.py tests/test_executor_no_translator_import.py
uv run mypy src
uv run pytest tests/test_translate_endpoint.py tests/test_prompt_injection.py tests/test_modes.py tests/test_executor_no_translator_import.py -v
uv run pytest                      # full suite stays green
pnpm -C . build && pnpm -C . test  # dashboard (NL window)
```
