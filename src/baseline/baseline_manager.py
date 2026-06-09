"""Baseline Manager for TestPilot SFCC — U2 core module.

Provides:
- Pure functions: calculate_p95, is_bootstrap_mode, compute_traffic_light.
- BaselineStore Protocol: storage abstraction (InMemoryBaselineStore for tests/local).
- BaselineManager: orchestrator that enforces the gate-only guard (C11).

Design invariants enforced here:
- Compound key ``(environment_id, profile_name, flow_name)`` prevents cross-environment
  baseline contamination (Gate 2 / Gate 4 of build-sequence.md).
- Only gate-mode runs feed the baseline; exploratory runs are silently dropped (C11).
- Bootstrap silence: compute_traffic_light always returns GREEN when bootstrap=True
  (Invariant #4 — no yellow alerts in the first 14 successful runs per combination).
- p95 is computed over the BASELINE_WINDOW most-recent runs (Invariant #5).
- The traffic light is 100% deterministic — no LLM, no external calls (P7/C10).

Traceability: RF-09, RNF-09, C11, Invariant #4, Invariant #5.
"""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

from src.models import (
    BaselineComparison,
    EnvironmentId,
    FlowName,
    Mode,
    ProfileId,
    RunRecord,
    TrafficLight,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

YELLOW_THRESHOLD: float = 1.2
"""Ratio above which the traffic light turns YELLOW."""

RED_THRESHOLD: float = 1.5
"""Ratio above which the traffic light turns RED."""

BOOTSTRAP_MIN_RUNS: int = 14
"""Invariant #4: no yellow alerts until 14 successful runs per combination."""

BASELINE_WINDOW: int = 10
"""Invariant #5: p95 is computed over the last BASELINE_WINDOW runs."""

# ---------------------------------------------------------------------------
# Internal types
# ---------------------------------------------------------------------------

_StoreKey = tuple[EnvironmentId, ProfileId, FlowName]
"""Compound key that prevents cross-environment baseline contamination."""

# ---------------------------------------------------------------------------
# Pure functions (no state, no side effects)
# ---------------------------------------------------------------------------


def calculate_p95(runs: list[RunRecord]) -> int:
    """Return the p95 duration (ms) over the successful runs in *runs*.

    - If *runs* is empty or contains no successful runs, returns 0.
    - Only ``status == "success"`` runs contribute to the calculation.
    - Uses ceiling index: ``ceil(0.95 * n) - 1`` (0-based, sorted ascending).

    Args:
        runs: List of RunRecord objects (any order, any status mix).

    Returns:
        p95 duration in milliseconds as an integer, or 0 when there are no
        successful runs to measure.
    """
    if not runs:
        return 0

    success_durations = sorted(
        r.duration_ms for r in runs if r.status == "success"
    )
    if not success_durations:
        return 0

    n = len(success_durations)
    index = math.ceil(0.95 * n) - 1
    return int(success_durations[index])


def is_bootstrap_mode(runs: list[RunRecord]) -> bool:
    """Return True if the combination has fewer than BOOTSTRAP_MIN_RUNS successes.

    Bootstrap mode means the system has not yet accumulated enough history to
    establish a reliable p95 baseline. During bootstrap, the traffic light is
    always GREEN (Invariant #4).

    Only ``status == "success"`` runs count towards the bootstrap exit threshold;
    failed or errored runs do NOT accelerate the exit from bootstrap.

    Args:
        runs: All stored runs for a ``(environment_id, profile, flow)`` combination.

    Returns:
        True while fewer than BOOTSTRAP_MIN_RUNS successful runs have been recorded.
    """
    success_count = sum(1 for r in runs if r.status == "success")
    return success_count < BOOTSTRAP_MIN_RUNS


def compute_traffic_light(
    current_ms: int,
    p95_ms: int,
    bootstrap: bool,
) -> TrafficLight:
    """Compute the deterministic deploy-gate verdict.

    Rules (applied in order):
    1. bootstrap=True  -> GREEN (Invariant #4: bootstrap silence)
    2. p95_ms == 0     -> GREEN (no prior baseline; no threshold to compare)
    3. ratio >= RED_THRESHOLD (1.5) -> RED
    4. ratio >= YELLOW_THRESHOLD (1.2) -> YELLOW
    5. otherwise -> GREEN

    This function is pure: no LLM calls, no I/O, no hidden state (P7/C10).

    Args:
        current_ms: Duration of the current run in milliseconds.
        p95_ms: The stored p95 baseline in milliseconds.
        bootstrap: True if the combination is still in bootstrap phase.

    Returns:
        A TrafficLight enum value.
    """
    if bootstrap:
        return TrafficLight.GREEN

    if p95_ms == 0:
        return TrafficLight.GREEN

    ratio = current_ms / p95_ms

    if ratio >= RED_THRESHOLD:
        return TrafficLight.RED

    if ratio >= YELLOW_THRESHOLD:
        return TrafficLight.YELLOW

    return TrafficLight.GREEN


# ---------------------------------------------------------------------------
# BaselineStore Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class BaselineStore(Protocol):
    """Persistence abstraction for baseline run records.

    Implementations must be safe to use with the compound key
    ``(environment_id, profile_name, flow_name)``.  The gate-only guard is
    enforced by BaselineManager — implementations never see exploratory runs.
    """

    def record_run(self, run: RunRecord) -> None:
        """Persist *run* in the collection for its compound key.

        Called **only** with gate-mode runs — the caller (BaselineManager) has
        already filtered out exploratory runs.

        Args:
            run: A gate-mode RunRecord to persist.
        """
        ...

    def get_runs(
        self,
        environment_id: EnvironmentId,
        profile_name: ProfileId,
        flow_name: FlowName,
        limit: int = BASELINE_WINDOW,
    ) -> list[RunRecord]:
        """Return the most-recent *limit* runs for the given compound key.

        Results are ordered descending by ``created_at`` (newest first).

        Args:
            environment_id: Target SFCC environment.
            profile_name: Browser profile identifier.
            flow_name: Flow identifier (never ``full_journey``).
            limit: Maximum number of runs to return. Defaults to BASELINE_WINDOW.

        Returns:
            List of RunRecord objects, ordered newest-first. Empty list if no
            records exist for the key.
        """
        ...

    def list_runs(
        self,
        environment_id: EnvironmentId,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RunRecord]:
        """Return a paginated list of all runs for *environment_id*.

        Ordered descending by ``created_at`` (newest first), then sliced by
        ``offset`` and ``limit``.

        Args:
            environment_id: Filter runs to this environment only.
            limit: Maximum number of runs to return.
            offset: Number of runs to skip from the start (0 = most-recent).

        Returns:
            List of RunRecord objects matching the pagination window.
        """
        ...


# ---------------------------------------------------------------------------
# InMemoryBaselineStore
# ---------------------------------------------------------------------------


class InMemoryBaselineStore:
    """In-memory implementation of BaselineStore.

    Suitable for unit tests and local development.  Production code uses the
    DynamoDB implementation (deferred to U4 / infra milestone).

    Data is keyed by ``_StoreKey = (environment_id, profile_name, flow_name)``
    to prevent cross-environment contamination (Gate 2 invariant).
    """

    def __init__(self) -> None:
        self._data: dict[_StoreKey, list[RunRecord]] = {}

    def record_run(self, run: RunRecord) -> None:
        """Append *run* to the list for its compound key."""
        key: _StoreKey = (run.environment_id, run.profile_name, run.flow_name)
        if key not in self._data:
            self._data[key] = []
        self._data[key].append(run)

    def get_runs(
        self,
        environment_id: EnvironmentId,
        profile_name: ProfileId,
        flow_name: FlowName,
        limit: int = BASELINE_WINDOW,
    ) -> list[RunRecord]:
        """Return the *limit* most-recent runs for the given compound key."""
        key: _StoreKey = (environment_id, profile_name, flow_name)
        runs = self._data.get(key, [])
        # Sort descending by created_at (newest first), then take first `limit`.
        sorted_runs = sorted(runs, key=lambda r: r.created_at, reverse=True)
        return sorted_runs[:limit]

    def list_runs(
        self,
        environment_id: EnvironmentId,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RunRecord]:
        """Return paginated runs for *environment_id* across all (profile, flow) keys."""
        all_runs: list[RunRecord] = []
        for (env_id, _profile, _flow), runs in self._data.items():
            if env_id == environment_id:
                all_runs.extend(runs)
        sorted_runs = sorted(all_runs, key=lambda r: r.created_at, reverse=True)
        return sorted_runs[offset : offset + limit]


# ---------------------------------------------------------------------------
# BaselineManager — orchestrator
# ---------------------------------------------------------------------------


class BaselineManager:
    """Orchestrates baseline storage with the gate-only guard.

    Callers (U3 reporter, U4 API) interact with this class, not with the store
    directly.  The gate-only guard is encapsulated here so callers never need to
    know about C11 — they simply pass the run mode and let BaselineManager decide.

    Args:
        store: A BaselineStore implementation (InMemoryBaselineStore in tests,
               DynamoDB store in production).
    """

    def __init__(self, store: BaselineStore) -> None:
        self._store = store

    def save_run(self, run: RunRecord, mode: Mode) -> None:
        """Persist *run* only if *mode* is ``"gate"`` (C11).

        Exploratory runs are silently ignored — no exception is raised.  This
        guard is the single enforcement point for C11 / Invariant #5.

        Args:
            run: The RunRecord to potentially persist.
            mode: The execution mode of the run (``"gate"`` or ``"exploratory"``).
        """
        if mode != "gate":
            return
        self._store.record_run(run)

    def get_baseline_comparison(
        self,
        environment_id: EnvironmentId,
        profile_name: ProfileId,
        flow_name: FlowName,
        current_ms: int,
    ) -> BaselineComparison:
        """Compute baseline comparison for the current run.

        Retrieves the BASELINE_WINDOW most-recent gate runs for the combination,
        calculates p95 and bootstrap status, and returns a BaselineComparison.

        Args:
            environment_id: Target SFCC environment of the current run.
            profile_name: Browser profile of the current run.
            flow_name: Flow executed in the current run.
            current_ms: Wall-clock duration of the current run in milliseconds.

        Returns:
            BaselineComparison with p95_ms, current_ms, bootstrap_mode, and
            runs_count populated.
        """
        # Fetch enough runs to determine bootstrap status (need up to BOOTSTRAP_MIN_RUNS).
        # We request max(BASELINE_WINDOW, BOOTSTRAP_MIN_RUNS) so that both the p95
        # window and the bootstrap threshold are correctly evaluated.
        fetch_limit = max(BASELINE_WINDOW, BOOTSTRAP_MIN_RUNS)
        all_recent_runs = self._store.get_runs(
            environment_id, profile_name, flow_name, fetch_limit
        )
        # p95 uses only the BASELINE_WINDOW most-recent runs (Invariant #5).
        window_runs = all_recent_runs[:BASELINE_WINDOW]
        p95 = calculate_p95(window_runs)
        # Bootstrap check uses the full fetch to count up to BOOTSTRAP_MIN_RUNS.
        bootstrap = is_bootstrap_mode(all_recent_runs)
        return BaselineComparison(
            p95_ms=p95,
            current_ms=current_ms,
            bootstrap_mode=bootstrap,
            runs_count=len(window_runs),
        )

    def list_runs(
        self,
        environment_id: EnvironmentId,
        limit: int,
        offset: int,
    ) -> list[RunRecord]:
        """Delegate paginated run listing to the underlying store.

        Args:
            environment_id: Filter runs to this environment.
            limit: Maximum number of runs to return.
            offset: Number of runs to skip from the start.

        Returns:
            Paginated list of RunRecord objects, newest first.
        """
        return self._store.list_runs(environment_id, limit, offset)
