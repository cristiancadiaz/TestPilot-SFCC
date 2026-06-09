"""RunOrchestrator (S1) — drive ``POST /v1/run`` end to end.

Resolves the environment, runs every profile×flow combination in parallel
(bounded by a semaphore, under a global watchdog timeout), generates the report
(U3), persists it, feeds gate-mode runs into the baseline (U2), and tracks live
status (S7).

Wave-1 limitation: only the flows present in the executor's ``FLOW_REGISTRY``
(``checkout_full``, ``checkout_card_declined``) are runnable. ``full_journey`` and
the journey flows are wave 2 — requested here they yield 422 ``validation_failed``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import cast

from src.api.errors import (
    InvariantViolatedError,
    RunTimeoutError,
    ValidationFailedError,
)
from src.api.schemas import RunState
from src.api.services.environment_resolver import EnvironmentResolver
from src.api.services.live_status_tracker import LiveStatusTracker
from src.api.stores import RunReportStore
from src.baseline import BaselineManager
from src.executor.profiles import ALL_PROFILES
from src.executor.runner import FLOW_REGISTRY
from src.executor.runner import run_profile as _default_run_profile
from src.models import (
    BrowserProfile,
    ExecutionReport,
    FlowName,
    FlowSelection,
    ProfileResult,
    ResolvedEnvironment,
    RunRecord,
    SyntheticUserConfig,
)
from src.reporter import generate_report

logger = logging.getLogger("testpilot.api.orchestrator")

MAX_CONCURRENT_PROFILES = 3
RUN_TIMEOUT_SECONDS = int(os.environ.get("RUN_TIMEOUT_SECONDS", "1800"))

_PROFILE_BY_NAME: dict[str, BrowserProfile] = {p.name: p for p in ALL_PROFILES}

RunProfileFn = Callable[
    [BrowserProfile, FlowName, SyntheticUserConfig, ResolvedEnvironment, str],
    Awaitable[ProfileResult],
]


class RunOrchestrator:
    """Orchestrate a full run from a validated config to a persisted report."""

    def __init__(
        self,
        resolver: EnvironmentResolver,
        baseline_manager: BaselineManager,
        report_store: RunReportStore,
        tracker: LiveStatusTracker,
        *,
        run_profile: RunProfileFn = _default_run_profile,
        timeout_seconds: int = RUN_TIMEOUT_SECONDS,
    ) -> None:
        self._resolver = resolver
        self._baseline = baseline_manager
        self._reports = report_store
        self._tracker = tracker
        self._run_profile = run_profile
        self._timeout = timeout_seconds

    @staticmethod
    def _resolve_flows(flows: list[FlowSelection]) -> list[FlowName]:
        """Validate requested flows against the wave-1 executor registry."""
        supported = set(FLOW_REGISTRY)
        resolved: list[FlowName] = []
        for flow in flows:
            if flow == "full_journey":
                raise ValidationFailedError(
                    "full_journey is not available in wave 1 "
                    "(FlowCatalog composition is wave 2)",
                    details={"flow": flow},
                )
            if flow not in supported:
                raise ValidationFailedError(
                    "flow is not available in wave 1",
                    details={"flow": flow, "supported": sorted(supported)},
                )
            resolved.append(cast(FlowName, flow))
        return resolved

    async def execute(self, config: SyntheticUserConfig) -> ExecutionReport:
        """Run *config* and return the persisted ``ExecutionReport``."""
        run_id = str(uuid.uuid4())
        env = self._resolver.resolve(config.environment_id)  # 404/409/502/422
        flows = self._resolve_flows(config.flows)
        profiles = [_PROFILE_BY_NAME[p] for p in config.profiles]
        combos = [(profile, flow) for profile in profiles for flow in flows]

        started_at = datetime.now(timezone.utc)
        self._tracker.start(
            run_id,
            config.environment_id,
            started_at,
            [(profile.name, flow) for profile, flow in combos],
        )

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROFILES)

        async def _run_one(profile: BrowserProfile, flow: FlowName) -> ProfileResult:
            async with semaphore:
                self._tracker.update_profile(
                    run_id, profile.name, flow, RunState.RUNNING
                )
                result = await self._run_profile(profile, flow, config, env, run_id)
                final = (
                    RunState.COMPLETED
                    if result.flow_result.status == "success"
                    else RunState.FAILED
                )
                self._tracker.update_profile(run_id, profile.name, flow, final)
                return result

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*[_run_one(p, f) for p, f in combos]),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError as exc:
            self._tracker.fail(run_id)
            raise RunTimeoutError(
                "run exceeded the maximum duration",
                details={"timeout_seconds": self._timeout},
            ) from exc

        finished_at = datetime.now(timezone.utc)

        # Zero-contamination invariant (#1) — critical incident if violated.
        for result in results:
            if result.flow_result.orders_created != 0:
                logger.critical(
                    "orders_created invariant violated",
                    extra={
                        "run_id": run_id,
                        "environment_id": config.environment_id,
                        "profile": result.profile.name,
                        "flow": result.flow_result.flow_name,
                    },
                )
                self._tracker.fail(run_id)
                raise InvariantViolatedError("orders_created != 0 detected")

        report = generate_report(
            run_id=run_id,
            environment_id=config.environment_id,
            mode=config.mode,
            started_at=started_at,
            finished_at=finished_at,
            profile_results=list(results),
            baseline_manager=self._baseline,
        )

        self._reports.save(report)
        # Persist into the baseline AFTER generating the report (so the current run
        # is never compared against itself). The gate-only guard lives in U2.
        for profile_result in report.profile_results:
            self._baseline.save_run(
                RunRecord(
                    run_id=run_id,
                    environment_id=config.environment_id,
                    profile_name=profile_result.profile.name,
                    flow_name=profile_result.flow_result.flow_name,
                    duration_ms=profile_result.flow_result.duration_ms,
                    status=profile_result.flow_result.status,
                    created_at=finished_at,
                ),
                config.mode,
            )

        self._tracker.complete(run_id, report.traffic_light)
        return report
