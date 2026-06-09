# U3 Reporter — Code Summary

> Gate 4 verified (2026-06-08). ruff + mypy --strict + pytest all green;
> JSON output validates against `specs/execution_report.schema.json` v2.
>
> Supersedes the earlier planning stub, which described `to_json_dict` as
> "camelCase" and a `percentDiff` field — **both incorrect**: the v2 schema is
> snake_case and has no `percentDiff`. See "Deviations" below.

---

## Files created

| File | Purpose |
|---|---|
| `src/reporter/__init__.py` | Public API re-export. U4 imports from `src.reporter` only. |
| `src/reporter/report_generator.py` | Verdict rules + report assembly + JSON/Markdown serialization. |
| `tests/test_reporter.py` | 15 deterministic unit tests (verdict matrix, schema validation, invariants). |
| `tests/test_reporter_pbt.py` | 1 property-based test (RNF-09): schema-valid + worst-of + no orders_created, 150 examples. |

## Gate 4 results

| Check | Result |
|---|---|
| `ruff check src/reporter/ tests/test_reporter*.py` | PASS |
| `mypy src/reporter/` (strict) | PASS — 2 source files |
| `pytest tests/test_reporter*.py` | PASS — 21 tests |
| Full suite | PASS — 110 tests |
| JSON validates vs `execution_report.schema.json` (Draft 2020-12) | PASS — green/yellow/red/bootstrap/failed/error + multi-profile |
| Markdown legible en CLI | PASS — `test_markdown_contains_verdict_and_invariant_line` |
| `orders_created=0` enforced | PASS — assert guard + absent from JSON + Markdown line |
| Baseline queried with run `environment_id` (no cross-env) | PASS — `test_baseline_queried_with_run_environment` |

## Deterministic verdict (the core of U3 — pure, no LLM, P7/C10)

**Per profile×flow** (`compute_profile_verdict`):
1. `status == "failed"` → RED (functional failure)
2. `status == "error"` → YELLOW (infra error)
3. `status == "success"` → `compute_traffic_light(duration_ms, p95_ms, bootstrap)` (U2)

**Global** = worst-of(per-profile), `RED > YELLOW > GREEN`.

U1 returns `ProfileResult.traffic_light = GREEN` as a placeholder; `generate_report`
replaces it with the real verdict after querying the baseline.

## Decisions applied (from the plan, HITL-approved 2026-06-08)

- **D-U3-1** — report-level `baseline_comparison` = the comparison of the combo that
  drove the global verdict (worst light; tie-break highest `current/p95` ratio);
  `null` when every combo is bootstrap or has no history. Impl: `_select_report_baseline`.
- **D-U3-2** — report-level `bootstrap_mode` = `True` iff **all** combos are bootstrap
  (informational; never changes a per-profile verdict). Impl: `_report_bootstrap`.
- **D-U3-3** — U3 is **read-only** on the baseline. `BaselineManager.save_run` (persisting
  the run) is U4's orchestration job — no DynamoDB writes from the reporter.

## Deviations from the original stub

- `to_json_dict` is `report.model_dump(mode="json")` — **snake_case**, no camelCase,
  no key remapping. The v2 schema and `ExecutionReport` already agree on field names.
- There is **no `percentDiff` field** — it is not in the v2 schema. The slowdown ratio
  is computed internally only to pick the report-level baseline (D-U3-1).
- `orders_created` is excluded from the contract by the model (`Field(exclude=True)`);
  the Markdown documents the invariant (BR-U3-01).
- `audit` (U6) and per-profile `network_summary` (U7) are out of scope; the v2 schema
  permits their absence, so wave-1 reports omit both and still validate.
- `duration_ms` is derived from `finished_at - started_at`, clamped to ≥ 0 (clock-skew
  guard) to satisfy the schema `minimum: 0`.

## Traceability

| Requirement | Implementation | Test |
|---|---|---|
| RF-09 — deterministic verdict | `compute_profile_verdict`, `_global_verdict` | verdict-matrix tests |
| Schema contract (v2) | `to_json_dict` = `model_dump(mode="json")` | `test_json_dict_validates_against_schema` |
| BR-U3-01 / invariant #1 | assert in `generate_report`; Markdown line | `test_generate_report_rejects_contaminated_flow`, `test_orders_created_absent_from_json_but_invariant_holds` |
| Invariant #4 (bootstrap silence) | delegated to U2 `compute_traffic_light` | `test_bootstrap_never_yellow_even_when_slow` |
| Invariant #5 (p95) / no cross-env | `get_baseline_comparison(environment_id, …)` | `test_baseline_queried_with_run_environment` |
| P7/C10 (#8) — no LLM in verdict | no LLM imports in `src/reporter` | code review |
| RNF-09 — PBT | `tests/test_reporter_pbt.py` | 150 examples |
