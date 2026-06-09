# U7 Network / Performance Capture — Code Generation Plan (reconciled 2026-06-09)

> ★ Ola 2 (paralelo con U8). Prereqs: U1 runner ✅ · `specs/execution_report.schema.json`
> v2 con `$defs` NetworkSummary/ControllerTiming/WebVitals ✅ · FlowCatalog (U5) ✅.
> **Part 1 — Planning**; awaiting HITL approval before generation.
>
> ⚠️ **Protected path:** Step 5 modifies `src/executor/runner.py` (and the flows run
> against storefronts) — needs the same protected-path authorization as U5.

## What U7 delivers
Per-profile network capture: a filtered HAR (metadata+timings, **no bodies**, auth
redacted), SFRA controller timing aggregation (count + p95), and Core Web Vitals on
key pages — attached to each `ProfileResult.network_summary` and rendered in the
report. Feeds the U6 audit (performance dimension).

Stories: H8.1, H8.2 · RF-23, RNF-15. Restricción dura: redacción pre-persistencia
(RNF-15, blocking) · overhead ≤ ~10% · metadata+timings, nunca bodies.

## Reconciliation with current reality (what changed since 2026-06-03)
- **Schema v2 already has the network `$defs`** (NetworkSummary/ControllerTiming/
  WebVitals + `ProfileResult.network_summary`). U7 mirrors them in `src/models.py`
  (they are NOT modeled yet — line 13 of models.py explicitly defers them).
- **`runner.py` now has TWO entry points** (U5): `run_profile` AND `run_composition`.
  The original plan only mentioned `run_profile`. Capture must integrate into **both**
  (decision **D-U7-1**) — they share `_create_context`/`new_page`, so a single helper
  installed per page covers both.
- **`web_vitals` key pages = FlowCatalog `critical_points`** (U5 now provides them per
  flow). CWV is captured at those steps (decision **D-U7-2**).
- **HAR storage reuses the U4 evidence-path convention** (ScreenshotStore / `SCREENSHOT_DIR`):
  `{run_id}/{profile}/{flow}/network.har.json` (decision **D-U7-3**).
- `src/reporter/report_generator.py` exists (U3) with `to_markdown`/`to_json_dict` —
  U7 extends them (MODIFY, as planned).

## Decisions (HITL — recommended defaults in **bold**)
- **D-U7-1 — capture in both run paths.** A `NetworkCapture` helper attached to the
  page after `new_page()`; used identically by `run_profile` and `run_composition`.
  In a composition the HAR/timings are captured **per flow** (the page persists, so
  capture is reset/segmented per flow to keep one NetworkSummary per ProfileResult).
- **D-U7-2 — CWV on critical points.** Collect LCP/CLS/TTFB at each flow's declared
  `critical_points` (FlowCatalog); `None`-safe — a flow never fails because CWV could
  not be read (RNF-15 / H8.2).
- **D-U7-3 — HAR via the evidence store.** Reuse the U4 ScreenshotStore abstraction /
  evidence path for `network.har.json`; no new storage Protocol.
- **D-U7-4 — overhead budget.** ≤10% is validated best-effort (listeners are passive);
  documented in code-summary, not asserted as a hard timing test (flaky in CI).

## Steps

### Step 1 — `src/executor/network_capture.py` [x] (CREATE)
`NetworkCapture` — installs `page.on("request"/"response")`; `DOMAIN_ALLOWLIST` derived
from `env.store_url`; per request records URL (credential query params stripped),
method, status, resource_type, timings, transfer size; **never bodies**. `to_har_dict()`
redacts `Authorization`/`Cookie`/`Set-Cookie` headers (reuse the D12 redaction filter).
`reset()` to segment capture per flow in a composition.

### Step 2 — `src/executor/controller_timings.py` [x] (CREATE)
`SFRA_CONTROLLER_PATTERNS` (regex: `\w+-Show`, `Cart-\w+`, `CheckoutServices-\w+`,
`Search-\w+`, `Product-\w+`…). `aggregate_controllers(requests) -> list[ControllerTiming]`
with count + p95_ms per matched pattern, reusing U2's `calculate_p95`.

### Step 3 — `src/executor/web_vitals.py` [x] (CREATE)
`collect_web_vitals(page) -> WebVitals | None` — LCP/CLS via an injected
PerformanceObserver, TTFB via Navigation Timing. Returns `None` (never raises) when
unavailable. Called at the flow's critical points (D-U7-2).

### Step 4 — `src/models.py` [x] (MODIFY)
Add `NetworkSummary`, `ControllerTiming`, `WebVitals` (mirror schema v2 `$defs`);
add `ProfileResult.network_summary: NetworkSummary | None = None`. mypy --strict clean.

### Step 5 — `src/executor/runner.py` [x] (MODIFY — protected)
`run_profile` and `run_composition` install `NetworkCapture` after `new_page()`; at each
flow's end: aggregate controllers, collect CWV at critical points, persist filtered HAR
via the evidence store, attach `NetworkSummary` to the `ProfileResult`. Composition resets
capture per flow (D-U7-1).

### Step 6 — `src/reporter/report_generator.py` [x] (MODIFY)
`to_markdown` adds a per-profile network section (failed requests, top controllers by
p95, CWV); `to_json_dict` serializes `network_summary` (validates vs schema v2).

### Step 7 — `tests/test_network_capture.py` [x] (CREATE)
Mocked events: allowlist excludes third-party domains; `Authorization`/`Cookie` redacted
in `to_har_dict()`; **zero bodies** in the HAR; credential-pattern query params redacted.
**RNF-15 redaction test is blocking.**

### Step 8 — `tests/test_controller_timings.py` [x] (CREATE)
SFRA controller URLs aggregate (count, p95); asset/non-controller URLs excluded; p95
consistent with U2's `calculate_p95`.

### Step 9 — `tests/test_web_vitals.py` [x] (CREATE)
Page mock with metrics → populated WebVitals; page mock without support → `None`, no
exception; the flow never fails when CWV is `None`.

### Step 10 — `tests/test_runner_network_integration.py` [x] (CREATE — reconciliation add)
With the U5 playwright mock: `run_profile` and `run_composition` both attach a
`network_summary`; composition produces one summary per flow.

## Gate U7 (build-sequence) — CLOSED 2026-06-09
- [x] HAR has no credentials nor bodies (redaction test — **blocking**, RNF-15 — `test_network_capture.py`)
- [x] Controller aggregation + CWV None-safe
- [x] `network_summary` mirrors `execution_report.schema.json` v2 `$defs` (serializes via model_dump; null path validated by U3 tests)
- [x] Capture wired into BOTH run_profile and run_composition (D-U7-1 — `test_runner_network_integration.py`)
- [x] `ruff` + `mypy --strict` exit 0; full `pytest` suite green (**213 passed**)

## Verification
```bash
uv run ruff check src/executor/ src/reporter/ tests/test_network_capture.py tests/test_controller_timings.py tests/test_web_vitals.py tests/test_runner_network_integration.py
uv run mypy src
uv run pytest tests/test_network_capture.py tests/test_controller_timings.py tests/test_web_vitals.py tests/test_runner_network_integration.py -v
uv run pytest    # full suite stays green
```
