# U2 Baseline Manager — Code Summary

> Gate 2 verified. All checks passed: ruff, mypy --strict, pytest (37 tests including PBT-02/03/07/08/09).

---

## Files created

| File | Purpose |
|---|---|
| `src/baseline/__init__.py` | Public API re-export. U3/U4 import from `src.baseline` only. |
| `src/baseline/baseline_manager.py` | Core module: constants, `_StoreKey` type, pure functions, `BaselineStore` Protocol, `InMemoryBaselineStore`, `BaselineManager`. |
| `tests/test_baseline_manager.py` | 28 deterministic unit tests covering all required cases from the plan. |
| `tests/test_baseline_pbt.py` | 5 property-based tests (PBT-02/03/07/08/09) + PBT-EXTRA environment separation. |

---

## Implementation decisions

### Compound key `(environment_id, profile_name, flow_name)`

`InMemoryBaselineStore._data` is typed as `dict[_StoreKey, list[RunRecord]]` where `_StoreKey = tuple[EnvironmentId, ProfileId, FlowName]`. This makes cross-environment contamination structurally impossible — sandbox and staging histories are stored under distinct keys and can never be mixed.

### Gate-only guard (C11) in `BaselineManager.save_run`

The guard `if mode != "gate": return` is the single enforcement point for C11. It is silent (no exception), as required. Callers (U3, U4) pass the `Mode` from the execution context and never need to know about C11 themselves.

### Bootstrap check vs. p95 window

`BASELINE_WINDOW = 10` and `BOOTSTRAP_MIN_RUNS = 14` are intentionally different values. `get_baseline_comparison` fetches `max(BASELINE_WINDOW, BOOTSTRAP_MIN_RUNS) = 14` runs to correctly determine bootstrap status, then slices to `BASELINE_WINDOW = 10` for p95 computation. Without this two-step approach, bootstrap could never exit (10 < 14). The plan pseudocode implied a single `get_runs` call; this refinement is necessary for correctness and is the only deviation from the plan pseudocode.

### Pure functions (`calculate_p95`, `is_bootstrap_mode`, `compute_traffic_light`)

All three are stateless and side-effect-free (no I/O, no LLM calls). `compute_traffic_light` applies the bootstrap check before any ratio arithmetic — a single `if bootstrap: return GREEN` at the top ensures Invariant #4 is enforced regardless of `current_ms` or `p95_ms` values.

### `BaselineStore` is a `@runtime_checkable` Protocol

Allows `isinstance(store, BaselineStore)` checks if needed by future DynamoDB integration tests, without requiring inheritance from a base class.

### `list_runs` pagination

Implemented via Python slice `sorted_runs[offset : offset + limit]`. Ordering is `created_at` descending (newest first) across all `(profile, flow)` pairs for the requested environment.

---

## Gate 2 results

| Check | Result |
|---|---|
| `ruff check src/baseline/ tests/test_baseline_*.py` | PASS — no errors |
| `mypy src/baseline/` | PASS — no issues (2 source files, strict mode) |
| `pytest tests/test_baseline_manager.py` | PASS — 28 tests |
| `pytest tests/test_baseline_pbt.py` | PASS — 9 tests (5 blocking PBT + PBT-EXTRA variants) |
| `InMemoryBaselineStore` separates by `environment_id` | PASS — `test_store_separates_by_environment_id` |
| `compute_traffic_light(bootstrap=True)` never YELLOW/RED | PASS — PBT-09 (200 examples) |
| Exploratory run ignored without exception | PASS — `test_save_run_exploratory_mode_ignored`, `test_save_run_exploratory_does_not_raise` |

---

## Traceability

| Requirement | Implementation | Test |
|---|---|---|
| RF-09 — compound key `(env, profile, flow)` | `_StoreKey`, `InMemoryBaselineStore` | `test_store_separates_by_environment_id` |
| RF-09 — `calculate_p95` | Pure function, ceil index | `test_calculate_p95_*`, PBT-03, PBT-07 |
| RF-09 — `is_bootstrap_mode` | Counts `status=="success"` only | `test_is_bootstrap_mode_*` |
| RF-09 — `compute_traffic_light` | Pure function, ratio thresholds | `test_compute_traffic_light_*`, PBT-08, PBT-09 |
| RF-09 — `list_runs` paginated | `InMemoryBaselineStore.list_runs` + `BaselineManager.list_runs` | `test_list_runs_pagination` |
| RNF-09 — PBT with hypothesis | `tests/test_baseline_pbt.py` | PBT-02, PBT-03, PBT-07, PBT-08, PBT-09 |
| C11 — exploratory runs excluded | `BaselineManager.save_run` guard | `test_save_run_exploratory_mode_ignored`, `test_save_run_exploratory_does_not_raise` |
| Invariant #4 — bootstrap silence | `compute_traffic_light`: bootstrap check first | PBT-09, `test_compute_traffic_light_bootstrap_always_green` |
| Invariant #5 — p95 over last 10 runs | `BASELINE_WINDOW=10`, window slice in `get_baseline_comparison` | `test_store_returns_last_n_runs`, `test_get_baseline_comparison_full` |

---

## Deviation from plan

`get_baseline_comparison` fetches `max(BASELINE_WINDOW, BOOTSTRAP_MIN_RUNS) = 14` runs instead of exactly `BASELINE_WINDOW = 10`. This is required for bootstrap to ever exit: `BOOTSTRAP_MIN_RUNS (14) > BASELINE_WINDOW (10)`, so fetching only 10 runs would make it impossible to count 14 successes. The plan pseudocode was ambiguous on this point; the implementation is fully consistent with the stated invariants (#4 and #5) and the gate criteria.
