"""LiveStatusTracker (S7) — in-memory state of in-flight runs for dashboard polling.

Served by ``GET /v1/runs/{id}/status``. State is in-memory with a FIFO ring buffer
(max ``MAX_RUNS`` runs) and a lock for thread safety. State is lost on ECS task
restart (MVP limitation) — the dashboard then falls back to ``GET /v1/runs/{id}``.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from datetime import datetime

from src.api.schemas import ProfileRunStatus, RunState, RunStatus
from src.models import EnvironmentId, FlowName, ProfileId, TrafficLight

MAX_RUNS = 100


class LiveStatusTracker:
    """Track the live state of runs in progress (in-memory, bounded, thread-safe)."""

    def __init__(self, max_runs: int = MAX_RUNS) -> None:
        self._max = max_runs
        self._lock = threading.Lock()
        self._runs: "OrderedDict[str, RunStatus]" = OrderedDict()

    def start(
        self,
        run_id: str,
        environment_id: EnvironmentId,
        started_at: datetime,
        combos: list[tuple[ProfileId, FlowName]],
    ) -> None:
        """Register a run as RUNNING with one pending entry per profile×flow combo."""
        with self._lock:
            if len(self._runs) >= self._max:
                self._runs.popitem(last=False)  # evict oldest (FIFO)
            self._runs[run_id] = RunStatus(
                run_id=run_id,
                environment_id=environment_id,
                state=RunState.RUNNING,
                started_at=started_at,
                profiles=[
                    ProfileRunStatus(
                        profile_name=profile, flow_name=flow, state=RunState.PENDING
                    )
                    for profile, flow in combos
                ],
            )

    def update_profile(
        self,
        run_id: str,
        profile_name: ProfileId,
        flow_name: FlowName,
        state: RunState,
        *,
        current_step: str | None = None,
        steps_completed: int | None = None,
    ) -> None:
        """Update one profile×flow entry's live state."""
        with self._lock:
            status = self._runs.get(run_id)
            if status is None:
                return
            for entry in status.profiles:
                if entry.profile_name == profile_name and entry.flow_name == flow_name:
                    entry.state = state
                    if current_step is not None:
                        entry.current_step = current_step
                    if steps_completed is not None:
                        entry.steps_completed = steps_completed
                    break

    def complete(self, run_id: str, traffic_light: TrafficLight) -> None:
        """Mark a run COMPLETED with its final verdict."""
        with self._lock:
            status = self._runs.get(run_id)
            if status is not None:
                status.state = RunState.COMPLETED
                status.traffic_light = traffic_light

    def fail(self, run_id: str) -> None:
        """Mark a run FAILED (e.g. on timeout)."""
        with self._lock:
            status = self._runs.get(run_id)
            if status is not None:
                status.state = RunState.FAILED

    def get(self, run_id: str) -> RunStatus | None:
        """Return the live status, or ``None`` if unknown / evicted."""
        with self._lock:
            return self._runs.get(run_id)
