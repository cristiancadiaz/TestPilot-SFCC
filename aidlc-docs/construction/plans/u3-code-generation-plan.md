# U3 Reporter — Code Generation Plan (reconciled to specs v2 + U1/U2 real APIs, 2026-06-08)

> **Part 1 — Planning.** This plan supersedes the earlier stub (which said
> "camelCase para schema validation" — **wrong**: the v2 schema is snake_case and
> `ExecutionReport` already mirrors it). Awaiting HITL approval before generation.

## Module purpose & boundary

U3 turns the raw execution outputs into the published `ExecutionReport`: it
**computes the deterministic traffic light** (per-profile and global), assembles
the report object, serializes it to JSON (validated against
`specs/execution_report.schema.json`) and renders a human-readable Markdown.

What is **already built** and U3 consumes (does NOT reimplement):

- **U1 executor** (`src/executor/runner.py::run_profile`) returns a `ProfileResult`
  with `flow_result` populated and `traffic_light=GREEN` **as a placeholder** — its
  docstring states "the reporter (U3) computes the real verdict from p95 baseline".
- **U2 baseline** (`src/baseline`): `BaselineManager.get_baseline_comparison(env, profile, flow, current_ms) -> BaselineComparison`
  and the pure `compute_traffic_light(current_ms, p95_ms, bootstrap) -> TrafficLight`
  (rules: bootstrap→GREEN; p95==0→GREEN; ratio≥1.5→RED; ratio≥1.2→YELLOW; else GREEN).
- **Models** (`src/models.py`): `ExecutionReport`, `ProfileResult`, `FlowResult`,
  `StepResult`, `BrowserProfile`, `BaselineComparison`, `TrafficLight` already mirror
  schema v2 exactly (snake_case; `orders_created` is `Field(exclude=True)`).

**Hard invariants U3 must honour**
- **#1 zero contamination (BR-U3-01):** assert `orders_created == 0` on the report and
  every `flow_result`; the JSON never publishes it, but the Markdown documents it.
- **#8 P7/C10:** the traffic light is computed **exclusively** by the deterministic
  p95 rule. U3 contains NO LLM calls and never lets any audit object move the verdict.
- **Module boundary:** U3 reads the baseline (`get_baseline_comparison`) but **never
  writes** it — persisting the current run (`save_run`) is U4's orchestration job
  (see decision D-U3-3). No DynamoDB access from U3.

**Out of scope (deferred, schema allows their absence):** the `audit` object (U6)
and per-profile `network_summary` (U7). Wave-1 reports omit both.

## Public API (`src/reporter/__init__.py` re-exports)

```python
def generate_report(
    run_id: str,
    environment_id: EnvironmentId,
    mode: Mode,
    started_at: datetime,
    finished_at: datetime,
    profile_results: list[ProfileResult],   # from U1, traffic_light = placeholder
    baseline_manager: BaselineManager,
) -> ExecutionReport: ...

def compute_profile_verdict(
    flow_result: FlowResult,
    baseline: BaselineComparison,
) -> TrafficLight: ...                       # pure deterministic rule

def to_json_dict(report: ExecutionReport) -> dict[str, Any]: ...   # snake_case, schema-valid
def to_markdown(report: ExecutionReport) -> str: ...
```

## Deterministic verdict rules (the heart of U3 — pure, no LLM)

**Per profile×flow** (`compute_profile_verdict`), applied in order:
1. `flow_result.status == "failed"` → **RED**  (functional failure of the app)
2. `flow_result.status == "error"`  → **YELLOW** (infra error; schema: yellow = degradation *or* infra error)
3. `flow_result.status == "success"` → `compute_traffic_light(flow_result.duration_ms, baseline.p95_ms, baseline.bootstrap_mode)` (U2)

**Global** (`ExecutionReport.traffic_light`) = **worst** of all per-profile verdicts
(`RED > YELLOW > GREEN`) — schema: "el peor semáforo entre todos los perfiles".

`generate_report` flow:
1. Compute `duration_ms = int((finished_at - started_at).total_seconds() * 1000)`.
2. For each incoming `ProfileResult`: query
   `baseline_manager.get_baseline_comparison(environment_id, profile.name, flow_result.flow_name, flow_result.duration_ms)`,
   then rebuild the `ProfileResult` with `traffic_light = compute_profile_verdict(...)`
   (replacing U1's GREEN placeholder).
3. Aggregate global `traffic_light` (worst-of) and report-level `bootstrap_mode` /
   `baseline_comparison` per decisions below.
4. `assert orders_created == 0` on every flow_result (BR-U3-01).
5. Build and return `ExecutionReport`.

## Open decisions (need HITL sign-off — recommended defaults in **bold**)

- **D-U3-1 — report-level `baseline_comparison` (single object, multiple combos).**
  The v2 report has one `baseline_comparison` but a run can have N profile×flow combos.
  **Recommend:** the comparison of the combo that *drove the global verdict* (the
  worst-light combo; tie-break = highest `current_ms/p95_ms` ratio). `null` if every
  combo is bootstrap or has no history. *(Alt: always null in multi-combo runs.)*
- **D-U3-2 — report-level `bootstrap_mode` semantics.**
  **Recommend:** `True` iff **all** executed combos are in bootstrap (the whole run is
  still in its learning phase). Informational only — never changes a per-profile verdict.
  *(Alt: `any` combo in bootstrap.)*
- **D-U3-3 — does U3 persist the current run to the baseline?**
  **Recommend: No.** U3 is read-only on the baseline; `BaselineManager.save_run(...)`
  for each combo is U4 orchestration (it owns the RunRecord build + DynamoDB store).
  Keeps the executor/reporter free of baseline writes (CLAUDE.md boundary).

## Steps

### Step 1 — `src/reporter/__init__.py` [x]
Public API re-export (`generate_report`, `compute_profile_verdict`, `to_json_dict`,
`to_markdown`). U4 imports only from `src.reporter`.

### Step 2 — `src/reporter/report_generator.py` [x]
- [x] `compute_profile_verdict(flow_result, baseline)` — pure, the 3-rule ladder above.
- [x] `_global_verdict(verdicts: list[TrafficLight]) -> TrafficLight` — worst-of.
- [x] `_select_report_baseline(...)` / `_report_bootstrap(...)` — per D-U3-1 / D-U3-2.
- [x] `generate_report(...)` — orchestrates; rebuilds ProfileResults; asserts `orders_created==0` (BR-U3-01).
- [x] `to_json_dict(report)` — `report.model_dump(mode="json")` (ISO datetimes, enums→str,
      `orders_created` already excluded; **snake_case**, no key remapping).
- [x] `to_markdown(report)` — verdict header with colour word, run metadata, per-profile
      section (flow status + steps table with state/error), baseline comparison line,
      and an explicit `orders_created: 0 ✓ (zero-contamination)` line (BR-U3-01).
- [x] No LLM imports; no `src.baseline` writes; no DynamoDB (P7/C10 + boundary).

### Step 3 — `tests/test_reporter.py` (deterministic) [x]
Verdict matrix (using an `InMemoryBaselineStore` seeded with `RunRecord`s):
- [x] success + fast (ratio<1.2) → GREEN
- [x] success + slow (1.2≤ratio<1.5) → YELLOW
- [x] success + very slow (ratio≥1.5) → RED
- [x] status=failed → RED (regardless of timing)
- [x] status=error → YELLOW
- [x] bootstrap (<14 successes) → GREEN even when very slow (Invariant #4)
- [x] global = worst-of across multiple profiles (e.g. GREEN+YELLOW+RED → RED)
- [x] `to_json_dict` output **validates** against `specs/execution_report.schema.json`
      (jsonschema Draft 2020-12) for green / yellow / red / bootstrap / multi-profile cases
- [x] `orders_created` is absent from JSON but `report.orders_created == 0` asserted
- [x] `generate_report` raises `AssertionError` if a flow_result has `orders_created != 0`
- [x] `to_markdown` contains the verdict word and the `orders_created: 0` line
- [x] baseline queried with the run's `environment_id` (no cross-env mixing)

### Step 4 — `tests/test_reporter_pbt.py` (property-based, RNF-09) [x]
- [x] PBT: for any hypothesis-generated valid report, `to_json_dict` always validates
      against the schema.
- [x] PBT: `to_markdown` never raises and always mentions the global verdict.
- [x] PBT: global verdict is always the worst of the per-profile verdicts.

### Step 5 — `aidlc-docs/construction/u3/code/code-summary.md` [x]
Files, decisions taken (D-U3-1/2/3 outcomes), Gate 4 results, traceability
(RF-09 verdict, schema contract, BR-U3-01), deviations.

## Gate 4 — promotion criteria (from build-sequence.md)
- [x] JSON output validates against `specs/execution_report.schema.json`
- [x] Markdown legible en CLI
- [x] Invariante `orders_created=0` enforced (assert + Markdown line)
- [x] Baseline consultado con `environment_id` (no se mezclan ambientes)
- [x] `ruff check` + `mypy --strict` exit 0; full `pytest` suite green

## Verification commands
```bash
uv run ruff check src/reporter/ tests/test_reporter*.py
uv run mypy src/reporter/
uv run pytest tests/test_reporter.py tests/test_reporter_pbt.py -v
uv run pytest    # full suite stays green
```
