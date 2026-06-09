from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, List, Tuple, cast, Literal

import hypothesis.strategies as st
from hypothesis import given

from src.baseline.baseline_manager import BaselineManager, InMemoryBaselineStore, calculate_p95, BASELINE_WINDOW
from src.models import RunRecord


@st.composite
def run_records(draw: Any, count: Any = st.integers(min_value=1, max_value=20)) -> List[Tuple[RunRecord, str]]:
    n = draw(count)
    records: List[Tuple[RunRecord, str]] = []
    now = datetime.now(timezone.utc)
    for i in range(n):
        duration = draw(st.integers(min_value=100, max_value=5000))
        status = draw(st.sampled_from(["success", "failed", "error"]))
        mode = draw(st.sampled_from(["gate", "exploratory"]))
        rec = RunRecord(
            run_id=str(i),
            environment_id="staging",
            profile_name="mobile_co",
            flow_name="pdp_validation",
            duration_ms=duration,
            status=status,
            created_at=now - timedelta(seconds=i),
        )
        # Attach mode as external parallel list via hypothesis drawing context
        records.append((rec, mode))
    return records


@given(run_records())
def test_baseline_excludes_exploratory(records_and_modes: List[Tuple[RunRecord, str]]) -> None:
    """Property: BaselineManager.save_run only persists gate-mode runs; p95 uses only gate runs."""
    bm = BaselineManager(InMemoryBaselineStore())
    # Save runs: use the associated mode to decide save or not
    gate_runs: List[RunRecord] = []
    for rec, mode in records_and_modes:
        # mypy: BaselineManager.save_run expects Literal['gate','exploratory'] for mode
        bm.save_run(rec, cast(Literal['gate', 'exploratory'], mode))
        if mode == "gate":
            gate_runs.append(rec)
    # Compute p95 over the BASELINE_WINDOW most-recent gate_runs using the pure function
    newest_window = sorted(gate_runs, key=lambda r: r.created_at, reverse=True)[:BASELINE_WINDOW]
    expected_p95 = calculate_p95(newest_window)
    # Use baseline manager to compute comparison for a hypothetical current run
    comparison = bm.get_baseline_comparison("staging", "mobile_co", "pdp_validation", 1234)
    assert comparison.p95_ms == expected_p95
    # runs_count in comparison should be <= BASELINE_WINDOW (10) and equals len(window of gate runs)
    assert comparison.runs_count <= 10
