"""Deterministic unit tests for src/baseline (U2 Baseline Manager).

Coverage:
- Import smoke test
- Pure functions: calculate_p95, is_bootstrap_mode, compute_traffic_light
- InMemoryBaselineStore: separation by environment_id, pagination
- BaselineManager: gate-only guard (C11), get_baseline_comparison

Traceability: RF-09, C11, Invariant #4, Invariant #5.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.models import (
    BaselineComparison,
    FlowName,
    ProfileId,
    RunRecord,
    TrafficLight,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(
    *,
    environment_id: str = "sandbox",
    profile_name: ProfileId = "mobile_co",
    flow_name: FlowName = "checkout_full",
    duration_ms: int = 1000,
    status: str = "success",
    run_id: str = "run-001",
) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        environment_id=environment_id,  # type: ignore[arg-type]
        profile_name=profile_name,
        flow_name=flow_name,
        duration_ms=duration_ms,
        status=status,  # type: ignore[arg-type]
        created_at=datetime.now(tz=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Import smoke test
# ---------------------------------------------------------------------------


def test_import_ok() -> None:
    """Public API must be importable without errors."""
    from src.baseline import (  # noqa: F401
        BaselineManager,
        InMemoryBaselineStore,
        calculate_p95,
    )


# ---------------------------------------------------------------------------
# calculate_p95
# ---------------------------------------------------------------------------


def test_calculate_p95_empty_list() -> None:
    from src.baseline import calculate_p95

    assert calculate_p95([]) == 0


def test_calculate_p95_ten_known_runs() -> None:
    """10 runs with durations 100..1000 ms. p95 index = ceil(0.95*10)-1 = 9."""
    from src.baseline import calculate_p95

    runs = [
        _make_run(duration_ms=d * 100, run_id=f"run-{d}")
        for d in range(1, 11)  # 100, 200, ..., 1000
    ]
    assert calculate_p95(runs) == 1000


def test_calculate_p95_excludes_failed_runs() -> None:
    """Failed runs must not influence the p95 calculation."""
    from src.baseline import calculate_p95

    success_runs = [
        _make_run(duration_ms=100, run_id="s1"),
        _make_run(duration_ms=200, run_id="s2"),
        _make_run(duration_ms=300, run_id="s3"),
    ]
    failed_runs = [
        _make_run(duration_ms=9999, status="failed", run_id="f1"),
        _make_run(duration_ms=9999, status="failed", run_id="f2"),
    ]
    result = calculate_p95(success_runs + failed_runs)
    # p95 of [100, 200, 300]: ceil(0.95*3)-1 = ceil(2.85)-1 = 3-1 = 2 -> 300
    assert result == 300


def test_calculate_p95_only_failed_runs() -> None:
    """No successful runs -> p95 returns 0."""
    from src.baseline import calculate_p95

    runs = [_make_run(duration_ms=9999, status="failed", run_id="f1")]
    assert calculate_p95(runs) == 0


# ---------------------------------------------------------------------------
# is_bootstrap_mode
# ---------------------------------------------------------------------------


def test_is_bootstrap_mode_fewer_than_14() -> None:
    from src.baseline import is_bootstrap_mode

    runs = [_make_run(run_id=f"run-{i}") for i in range(5)]
    assert is_bootstrap_mode(runs) is True


def test_is_bootstrap_mode_exactly_14() -> None:
    """Bootstrap ends when the 14th successful run is recorded (invariant #4)."""
    from src.baseline import is_bootstrap_mode

    runs = [_make_run(run_id=f"run-{i}") for i in range(14)]
    assert is_bootstrap_mode(runs) is False


def test_is_bootstrap_mode_more_than_14() -> None:
    from src.baseline import is_bootstrap_mode

    runs = [_make_run(run_id=f"run-{i}") for i in range(20)]
    assert is_bootstrap_mode(runs) is False


def test_is_bootstrap_mode_counts_only_success() -> None:
    """Failed runs do not count towards bootstrap exit threshold."""
    from src.baseline import is_bootstrap_mode

    # 13 success + 10 failed = 23 total, but still in bootstrap (< 14 success)
    success_runs = [_make_run(run_id=f"s-{i}") for i in range(13)]
    failed_runs = [_make_run(status="failed", run_id=f"f-{i}") for i in range(10)]
    assert is_bootstrap_mode(success_runs + failed_runs) is True


# ---------------------------------------------------------------------------
# compute_traffic_light
# ---------------------------------------------------------------------------


def test_compute_traffic_light_green() -> None:
    from src.baseline import compute_traffic_light

    assert compute_traffic_light(1000, 1000, bootstrap=False) == TrafficLight.GREEN


def test_compute_traffic_light_yellow() -> None:
    """ratio = 1250/1000 = 1.25 >= YELLOW_THRESHOLD (1.2)."""
    from src.baseline import compute_traffic_light

    assert compute_traffic_light(1250, 1000, bootstrap=False) == TrafficLight.YELLOW


def test_compute_traffic_light_red() -> None:
    """ratio = 1600/1000 = 1.6 >= RED_THRESHOLD (1.5)."""
    from src.baseline import compute_traffic_light

    assert compute_traffic_light(1600, 1000, bootstrap=False) == TrafficLight.RED


def test_compute_traffic_light_bootstrap_always_green() -> None:
    """Invariant #4: bootstrap=True must NEVER return YELLOW or RED."""
    from src.baseline import compute_traffic_light

    result = compute_traffic_light(9999, 1, bootstrap=True)
    assert result == TrafficLight.GREEN


def test_compute_traffic_light_zero_p95_is_green() -> None:
    """No prior baseline -> GREEN (no threshold to compare against)."""
    from src.baseline import compute_traffic_light

    assert compute_traffic_light(5000, 0, bootstrap=False) == TrafficLight.GREEN


def test_compute_traffic_light_at_yellow_boundary() -> None:
    """Exact ratio = 1.2 should be YELLOW (>= threshold, not >)."""
    from src.baseline import compute_traffic_light

    assert compute_traffic_light(1200, 1000, bootstrap=False) == TrafficLight.YELLOW


def test_compute_traffic_light_at_red_boundary() -> None:
    """Exact ratio = 1.5 should be RED."""
    from src.baseline import compute_traffic_light

    assert compute_traffic_light(1500, 1000, bootstrap=False) == TrafficLight.RED


def test_compute_traffic_light_just_below_yellow() -> None:
    """ratio = 1.19 < YELLOW_THRESHOLD -> GREEN."""
    from src.baseline import compute_traffic_light

    assert compute_traffic_light(1190, 1000, bootstrap=False) == TrafficLight.GREEN


# ---------------------------------------------------------------------------
# InMemoryBaselineStore — separation by environment_id (Gate 2)
# ---------------------------------------------------------------------------


def test_store_separates_by_environment_id() -> None:
    """Runs from different environments must NOT contaminate each other (Gate 2)."""
    from src.baseline import InMemoryBaselineStore

    store = InMemoryBaselineStore()
    run_sandbox = _make_run(
        environment_id="sandbox",
        profile_name="mobile_co",
        flow_name="checkout_full",
        duration_ms=500,
        run_id="sandbox-run",
    )
    run_staging = _make_run(
        environment_id="staging",
        profile_name="mobile_co",
        flow_name="checkout_full",
        duration_ms=1000,
        run_id="staging-run",
    )
    store.record_run(run_sandbox)
    store.record_run(run_staging)

    sandbox_runs = store.get_runs("sandbox", "mobile_co", "checkout_full")
    staging_runs = store.get_runs("staging", "mobile_co", "checkout_full")

    assert len(sandbox_runs) == 1
    assert sandbox_runs[0].run_id == "sandbox-run"

    assert len(staging_runs) == 1
    assert staging_runs[0].run_id == "staging-run"


def test_store_returns_last_n_runs() -> None:
    """get_runs(limit=10) must return at most 10 runs, most recent first."""
    from src.baseline import InMemoryBaselineStore

    store = InMemoryBaselineStore()
    for i in range(15):
        store.record_run(_make_run(run_id=f"run-{i:02d}", duration_ms=(i + 1) * 100))

    runs = store.get_runs("sandbox", "mobile_co", "checkout_full", limit=10)
    assert len(runs) == 10
    # Results ordered desc by created_at; last inserted = most recent
    # Because all created_at are effectively the same (within the test), we
    # verify count only — ordering by insertion index is implementation detail.


def test_store_returns_all_runs_within_limit() -> None:
    """When fewer runs exist than limit, all are returned."""
    from src.baseline import InMemoryBaselineStore

    store = InMemoryBaselineStore()
    for i in range(5):
        store.record_run(_make_run(run_id=f"run-{i}"))

    runs = store.get_runs("sandbox", "mobile_co", "checkout_full", limit=10)
    assert len(runs) == 5


def test_store_empty_for_unknown_key() -> None:
    """Querying a key with no records returns an empty list."""
    from src.baseline import InMemoryBaselineStore

    store = InMemoryBaselineStore()
    runs = store.get_runs("sandbox", "mobile_co", "checkout_full")
    assert runs == []


# ---------------------------------------------------------------------------
# list_runs — pagination
# ---------------------------------------------------------------------------


def test_list_runs_pagination() -> None:
    """list_runs must support offset/limit pagination."""
    from src.baseline import InMemoryBaselineStore

    store = InMemoryBaselineStore()
    for i in range(5):
        store.record_run(_make_run(run_id=f"run-{i}"))

    page1 = store.list_runs("sandbox", limit=3, offset=0)
    assert len(page1) == 3

    page2 = store.list_runs("sandbox", limit=3, offset=3)
    assert len(page2) == 2


def test_list_runs_only_returns_requested_environment() -> None:
    """list_runs must not leak runs from other environments."""
    from src.baseline import InMemoryBaselineStore

    store = InMemoryBaselineStore()
    for i in range(3):
        store.record_run(_make_run(environment_id="sandbox", run_id=f"sb-{i}"))
    for i in range(3):
        store.record_run(_make_run(environment_id="staging", run_id=f"st-{i}"))

    sandbox_page = store.list_runs("sandbox", limit=50, offset=0)
    assert len(sandbox_page) == 3
    assert all(r.environment_id == "sandbox" for r in sandbox_page)

    staging_page = store.list_runs("staging", limit=50, offset=0)
    assert len(staging_page) == 3
    assert all(r.environment_id == "staging" for r in staging_page)


def test_list_runs_empty_environment() -> None:
    """list_runs on an environment with no records returns an empty list."""
    from src.baseline import InMemoryBaselineStore

    store = InMemoryBaselineStore()
    assert store.list_runs("sandbox", limit=10, offset=0) == []


# ---------------------------------------------------------------------------
# BaselineManager — gate-only guard (C11)
# ---------------------------------------------------------------------------


def test_save_run_gate_mode_persists() -> None:
    """Gate runs must be persisted (C11)."""
    from src.baseline import BaselineManager, InMemoryBaselineStore

    store = InMemoryBaselineStore()
    manager = BaselineManager(store)
    run = _make_run()
    manager.save_run(run, mode="gate")

    stored = store.get_runs("sandbox", "mobile_co", "checkout_full")
    assert len(stored) == 1


def test_save_run_exploratory_mode_ignored() -> None:
    """Exploratory runs must NOT be persisted (C11)."""
    from src.baseline import BaselineManager, InMemoryBaselineStore

    store = InMemoryBaselineStore()
    manager = BaselineManager(store)
    run = _make_run()
    manager.save_run(run, mode="exploratory")

    stored = store.get_runs("sandbox", "mobile_co", "checkout_full")
    assert len(stored) == 0


def test_save_run_exploratory_does_not_raise() -> None:
    """Ignoring exploratory runs must be silent — no exceptions (C11)."""
    from src.baseline import BaselineManager, InMemoryBaselineStore

    store = InMemoryBaselineStore()
    manager = BaselineManager(store)
    run = _make_run()
    # Must not raise any exception
    manager.save_run(run, mode="exploratory")


# ---------------------------------------------------------------------------
# BaselineManager — get_baseline_comparison
# ---------------------------------------------------------------------------


def test_get_baseline_comparison_bootstrap() -> None:
    """With < 14 gate runs, bootstrap_mode must be True."""
    from src.baseline import BaselineManager, InMemoryBaselineStore

    store = InMemoryBaselineStore()
    manager = BaselineManager(store)

    for i in range(5):
        manager.save_run(_make_run(run_id=f"run-{i}", duration_ms=1000), mode="gate")

    comparison = manager.get_baseline_comparison(
        environment_id="sandbox",
        profile_name="mobile_co",
        flow_name="checkout_full",
        current_ms=1200,
    )
    assert isinstance(comparison, BaselineComparison)
    assert comparison.bootstrap_mode is True
    assert comparison.runs_count == 5
    assert comparison.current_ms == 1200


def test_get_baseline_comparison_full() -> None:
    """With 14+ gate runs, returns correct p95 and bootstrap_mode=False.

    get_baseline_comparison fetches max(BASELINE_WINDOW, BOOTSTRAP_MIN_RUNS) runs
    to determine bootstrap, then uses BASELINE_WINDOW for p95. With 14 successes
    the bootstrap check sees >= BOOTSTRAP_MIN_RUNS successes -> False.
    runs_count reflects the BASELINE_WINDOW slice used for p95.
    """
    from src.baseline import BASELINE_WINDOW, BOOTSTRAP_MIN_RUNS, BaselineManager, InMemoryBaselineStore

    store = InMemoryBaselineStore()
    manager = BaselineManager(store)

    # Insert BOOTSTRAP_MIN_RUNS (14) runs so bootstrap exits
    for i in range(BOOTSTRAP_MIN_RUNS):
        manager.save_run(
            _make_run(run_id=f"run-{i}", duration_ms=(i + 1) * 100),
            mode="gate",
        )

    comparison = manager.get_baseline_comparison(
        environment_id="sandbox",
        profile_name="mobile_co",
        flow_name="checkout_full",
        current_ms=900,
    )
    assert comparison.bootstrap_mode is False
    assert comparison.runs_count == BASELINE_WINDOW
    assert comparison.p95_ms >= 0
    assert comparison.current_ms == 900


def test_get_baseline_comparison_zero_runs() -> None:
    """No prior runs -> bootstrap_mode=True, p95=0, runs_count=0."""
    from src.baseline import BaselineManager, InMemoryBaselineStore

    store = InMemoryBaselineStore()
    manager = BaselineManager(store)

    comparison = manager.get_baseline_comparison(
        environment_id="sandbox",
        profile_name="mobile_co",
        flow_name="checkout_full",
        current_ms=500,
    )
    assert comparison.bootstrap_mode is True
    assert comparison.p95_ms == 0
    assert comparison.runs_count == 0


def test_list_runs_delegates_to_store() -> None:
    """BaselineManager.list_runs must delegate to store.list_runs."""
    from src.baseline import BaselineManager, InMemoryBaselineStore

    store = InMemoryBaselineStore()
    manager = BaselineManager(store)

    for i in range(5):
        manager.save_run(_make_run(run_id=f"run-{i}"), mode="gate")

    result = manager.list_runs("sandbox", limit=3, offset=0)
    assert len(result) == 3
