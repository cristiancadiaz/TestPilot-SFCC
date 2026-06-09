"""RunOrchestrator (S1) — drive ``POST /v1/run`` end to end.

Resolves the environment, runs every profile×flow combination in parallel
(bounded by a semaphore, under a global watchdog timeout), generates the report
(U3), persists it, feeds gate-mode runs into the baseline (U2), and tracks live
status (S7).

Flows are expanded by the closed ``flow_catalog`` (``full_journey`` → its declared
sequence; out-of-catalog → 422 ``validation_failed``). When a composition alias is
requested it runs as a chained ``run_composition`` per profile (shared browser
context); otherwise each profile×flow runs independently via ``run_profile``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

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
from src.executor import flow_catalog
from src.executor.profiles import ALL_PROFILES
from src.executor.runner import run_composition as _default_run_composition
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

RunCompositionFn = Callable[
    [BrowserProfile, list[FlowName], SyntheticUserConfig, ResolvedEnvironment, str],
    Awaitable[list[ProfileResult]],
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
        run_composition: RunCompositionFn = _default_run_composition,
        timeout_seconds: int = RUN_TIMEOUT_SECONDS,
    ) -> None:
        self._resolver = resolver
        self._baseline = baseline_manager
        self._reports = report_store
        self._tracker = tracker
        self._run_profile = run_profile
        self._run_composition = run_composition
        self._timeout = timeout_seconds

    @staticmethod
    def _expand_flows(flows: list[FlowSelection]) -> list[FlowName]:
        """Expand composition aliases via the closed catalog (invariant #2).

        ``full_journey`` becomes its declared modular sequence; out-of-catalog
        values raise ``ValidationFailedError`` (422). The catalog grows ONLY via
        curated PR — the orchestrator never dispatches an arbitrary flow.
        """
        try:
            return flow_catalog.expand_flows(flows)
        except ValueError as exc:
            raise ValidationFailedError(
                "flow is not in the closed catalog",
                details={"flows": list(flows)},
            ) from exc

    async def execute(self, config: SyntheticUserConfig) -> ExecutionReport:
        """Run *config* and return the persisted ``ExecutionReport``."""
        run_id = str(uuid.uuid4())
        env = self._resolver.resolve(config.environment_id)  # 404/409/502/422
        flows = self._expand_flows(config.flows)
        composition = flow_catalog.is_composition(config.flows)
        profiles = [_PROFILE_BY_NAME[p] for p in config.profiles]

        started_at = datetime.now(timezone.utc)
        self._tracker.start(
            run_id,
            config.environment_id,
            started_at,
            [(profile.name, flow) for profile in profiles for flow in flows],
        )

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROFILES)

        def _final_state(result: ProfileResult) -> RunState:
            return (
                RunState.COMPLETED
                if result.flow_result.status == "success"
                else RunState.FAILED
            )

        async def _run_flow(
            profile: BrowserProfile, flow: FlowName
        ) -> list[ProfileResult]:
            async with semaphore:
                self._tracker.update_profile(
                    run_id, profile.name, flow, RunState.RUNNING
                )
                result = await self._run_profile(profile, flow, config, env, run_id)
                self._tracker.update_profile(
                    run_id, profile.name, flow, _final_state(result)
                )
                return [result]

        async def _run_chain(profile: BrowserProfile) -> list[ProfileResult]:
            async with semaphore:
                for flow in flows:
                    self._tracker.update_profile(
                        run_id, profile.name, flow, RunState.RUNNING
                    )
                chain = await self._run_composition(profile, flows, config, env, run_id)
                for result in chain:
                    self._tracker.update_profile(
                        run_id,
                        profile.name,
                        result.flow_result.flow_name,
                        _final_state(result),
                    )
                return chain

        if composition:
            tasks = [_run_chain(profile) for profile in profiles]
        else:
            tasks = [_run_flow(p, f) for p in profiles for f in flows]

        try:
            grouped = await asyncio.wait_for(
                asyncio.gather(*tasks),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError as exc:
            self._tracker.fail(run_id)
            raise RunTimeoutError(
                "run exceeded the maximum duration",
                details={"timeout_seconds": self._timeout},
            ) from exc

        results: list[ProfileResult] = [r for group in grouped for r in group]

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
