"""Property-Based Tests (PBT) for src/baseline using hypothesis.

All PBT-02, PBT-03, PBT-07, PBT-08, PBT-09 are BLOCKING for Gate 2.
PBT-EXTRA (environment separation) is recommended but non-blocking.

Traceability: RF-09, RNF-09, C11, Invariant #4, Invariant #5.
"""

from __future__ import annotations

import random
from datetime import timezone

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import SearchStrategy

from src.baseline import (
    InMemoryBaselineStore,
    calculate_p95,
    compute_traffic_light,
)
from src.models import (
    BaselineComparison,
    FlowName,
    ProfileId,
    RunRecord,
    TrafficLight,
)

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_ENV_IDS = st.sampled_from(["sandbox", "development", "staging"])
_PROFILES: SearchStrategy[ProfileId] = st.sampled_from(
    ["mobile_co", "desktop_co", "desktop_ec"]
)
_FLOW_NAMES: SearchStrategy[FlowName] = st.sampled_from(
    [
        "checkout_full",
        "checkout_card_declined",
        "search_and_filter",
        "browse_discounted_products",
        "pdp_validation",
        "cart_review",
    ]
)
_STATUSES = st.sampled_from(["success", "failed", "error"])
_DURATIONS = st.integers(min_value=0, max_value=600_000)


def _gate_run_strategy(
    env_id: str = "sandbox",
    profile: ProfileId = "mobile_co",
    flow: FlowName = "checkout_full",
) -> SearchStrategy[RunRecord]:
    """Reusable strategy for a gate-mode successful RunRecord."""
    return st.builds(
        RunRecord,
        run_id=st.uuids().map(str),
        environment_id=st.just(env_id),
        profile_name=st.just(profile),
        flow_name=st.just(flow),
        duration_ms=_DURATIONS,
        status=st.just("success"),
        created_at=st.datetimes(timezones=st.just(timezone.utc)),
    )


def _run_with_status_strategy(
    env_id: str = "sandbox",
    profile: ProfileId = "mobile_co",
    flow: FlowName = "checkout_full",
) -> SearchStrategy[RunRecord]:
    """Strategy for RunRecord with mixed status (success/failed/error)."""
    return st.builds(
        RunRecord,
        run_id=st.uuids().map(str),
        environment_id=st.just(env_id),
        profile_name=st.just(profile),
        flow_name=st.just(flow),
        duration_ms=_DURATIONS,
        status=_STATUSES,
        created_at=st.datetimes(timezones=st.just(timezone.utc)),
    )


# ---------------------------------------------------------------------------
# PBT-02: Round-trip BaselineComparison
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(
    runs=st.lists(_gate_run_strategy(), min_size=0, max_size=30),
    current_ms=st.integers(min_value=0, max_value=600_000),
)
def test_pbt_02_baseline_comparison_round_trip(
    runs: list[RunRecord], current_ms: int
) -> None:
    """PBT-02: BaselineComparison can be serialized and reconstructed without data loss.

    Covers RF-09 model integrity.
    """
    from src.baseline import is_bootstrap_mode

    p95 = calculate_p95(runs)
    bootstrap = is_bootstrap_mode(runs)

    comparison = BaselineComparison(
        p95_ms=p95,
        current_ms=current_ms,
        bootstrap_mode=bootstrap,
        runs_count=len(runs),
    )

    # Round-trip: serialize to dict, reconstruct
    data = comparison.model_dump()
    reconstructed = BaselineComparison(**data)

    assert reconstructed.p95_ms == comparison.p95_ms
    assert reconstructed.current_ms == comparison.current_ms
    assert reconstructed.bootstrap_mode == comparison.bootstrap_mode
    assert reconstructed.runs_count == comparison.runs_count


# ---------------------------------------------------------------------------
# PBT-03: calculate_p95 is invariant to insertion order
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(
    runs=st.lists(_gate_run_strategy(), min_size=1, max_size=50),
)
def test_pbt_03_calculate_p95_order_invariant(runs: list[RunRecord]) -> None:
    """PBT-03: calculate_p95 must return the same value regardless of run order."""
    original_result = calculate_p95(runs)

    shuffled = runs[:]
    random.shuffle(shuffled)
    shuffled_result = calculate_p95(shuffled)

    assert original_result == shuffled_result


# ---------------------------------------------------------------------------
# PBT-07: calculate_p95 is bounded by [min_success_duration, max_success_duration]
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(
    runs=st.lists(_run_with_status_strategy(), min_size=1, max_size=50),
)
def test_pbt_07_calculate_p95_bounded(runs: list[RunRecord]) -> None:
    """PBT-07: p95 must be within [min, max] of successful run durations.

    Fundamental property of any percentile function.
    """
    success_durations = [r.duration_ms for r in runs if r.status == "success"]

    if not success_durations:
        # No successful runs -> p95 must return 0
        assert calculate_p95(runs) == 0
        return

    result = calculate_p95(runs)
    assert min(success_durations) <= result <= max(success_durations), (
        f"p95={result} out of bounds [{min(success_durations)}, {max(success_durations)}] "
        f"for durations {sorted(success_durations)}"
    )


# ---------------------------------------------------------------------------
# PBT-08: compute_traffic_light is deterministic (same input -> same output)
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(
    current_ms=st.integers(min_value=0, max_value=600_000),
    p95_ms=st.integers(min_value=0, max_value=600_000),
    bootstrap=st.booleans(),
)
def test_pbt_08_compute_traffic_light_deterministic(
    current_ms: int, p95_ms: int, bootstrap: bool
) -> None:
    """PBT-08: compute_traffic_light returns the same result for the same inputs.

    No hidden state, no randomness — pure function (P7/C10).
    """
    result1 = compute_traffic_light(current_ms, p95_ms, bootstrap)
    result2 = compute_traffic_light(current_ms, p95_ms, bootstrap)
    assert result1 == result2


# ---------------------------------------------------------------------------
# PBT-09: bootstrap=True NEVER returns YELLOW or RED (CRITICAL — Invariant #4)
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(
    current_ms=st.integers(min_value=0, max_value=600_000),
    p95_ms=st.integers(min_value=1, max_value=600_000),
)
def test_pbt_09_bootstrap_never_yellow_or_red(current_ms: int, p95_ms: int) -> None:
    """PBT-09: compute_traffic_light with bootstrap=True must ALWAYS return GREEN.

    Invariant #4 (bootstrap silence): no yellow alerts during the first 14
    successful runs per profile x flow combination.
    This is the most critical Gate 2 property test.
    """
    result = compute_traffic_light(current_ms, p95_ms, bootstrap=True)
    assert result not in {TrafficLight.YELLOW, TrafficLight.RED}, (
        f"bootstrap=True returned {result} for current_ms={current_ms}, p95_ms={p95_ms}"
    )
    assert result == TrafficLight.GREEN


# ---------------------------------------------------------------------------
# PBT-EXTRA: environment separation (recommended, non-blocking)
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(
    sandbox_runs=st.lists(
        _gate_run_strategy(env_id="sandbox"),
        min_size=0,
        max_size=20,
    ),
    staging_runs=st.lists(
        _gate_run_strategy(env_id="staging"),
        min_size=0,
        max_size=20,
    ),
)
def test_pbt_extra_environment_separation(
    sandbox_runs: list[RunRecord], staging_runs: list[RunRecord]
) -> None:
    """PBT-EXTRA: InMemoryBaselineStore must not mix runs across environments.

    After inserting sandbox and staging runs, querying one environment must
    never return runs from the other (compound key invariant).
    """
    store = InMemoryBaselineStore()

    for run in sandbox_runs:
        store.record_run(run)
    for run in staging_runs:
        store.record_run(run)

    retrieved_sandbox = store.get_runs("sandbox", "mobile_co", "checkout_full", limit=9999)
    retrieved_staging = store.get_runs("staging", "mobile_co", "checkout_full", limit=9999)

    # Filter to the specific (profile, flow) combination used in the strategy
    sandbox_ids = {r.run_id for r in sandbox_runs}
    staging_ids = {r.run_id for r in staging_runs}

    for run in retrieved_sandbox:
        assert run.run_id not in staging_ids, (
            f"Sandbox query returned staging run {run.run_id}"
        )

    for run in retrieved_staging:
        assert run.run_id not in sandbox_ids, (
            f"Staging query returned sandbox run {run.run_id}"
        )
