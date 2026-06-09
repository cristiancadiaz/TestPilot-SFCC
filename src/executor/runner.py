"""Executor runner — launches a Playwright browser and runs a single flow.

``run_profile`` is the public entry point consumed by the orchestrator (U4).
It:
  - Creates a browser context configured for the given ``BrowserProfile``.
  - Dispatches the requested flow via the closed FLOW_REGISTRY (invariant #2).
  - Captures ``InfrastructureError`` (network/DNS/Playwright crash) and returns
    a ``ProfileResult`` with ``status="error"`` instead of propagating.
  - NEVER resolves credentials — those arrive fully resolved in ``env`` (ADR-001).
  - Asserts ``orders_created == 0`` before returning (invariant #1).

Logging: module-level logger; credentials are NEVER written to logs (RNF-03).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Coroutine
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
)
from playwright.async_api import Error as PlaywrightError

from src.executor.controller_timings import aggregate_controllers
from src.executor.flow_catalog import FLOW_REGISTRY
from src.executor.network_capture import NetworkCapture
from src.executor.web_vitals import collect_web_vitals
from src.models import (
    BrowserProfile,
    FlowName,
    FlowResult,
    NetworkSummary,
    ProfileResult,
    ResolvedEnvironment,
    StepResult,
    SyntheticUserConfig,
    TrafficLight,
)

logger = logging.getLogger(__name__)


async def _build_network_summary(
    page: Page,
    capture: NetworkCapture,
    run_id: str,
    profile_id: str,
    flow_name: str,
) -> NetworkSummary:
    """Aggregate controllers, collect CWV, persist the redacted HAR, and summarize."""
    controllers = aggregate_controllers(capture.records)
    web_vitals = await collect_web_vitals(page)
    har_url = _persist_har(capture, run_id, profile_id, flow_name)
    return capture.build_summary(
        controllers=controllers, web_vitals=web_vitals, har_url=har_url
    )


def _persist_har(
    capture: NetworkCapture, run_id: str, profile_id: str, flow_name: str
) -> str:
    """Write the filtered HAR to ``SCREENSHOT_DIR`` if set; return its logical key.

    The key follows the ADR-003 evidence convention. When ``SCREENSHOT_DIR`` is
    unset (e.g. AWS path) the upload is handled by the infra adapters — we still
    return the key so ``har_url`` is populated. A write failure never aborts a run.
    """
    key = f"{run_id}/{profile_id}/{flow_name}/network.har.json"
    base = os.environ.get("SCREENSHOT_DIR")
    if base:
        try:
            path = os.path.join(base, *key.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(capture.to_har_dict(), handle)
        except OSError as exc:
            logger.warning("HAR persist failed (%s): %s", key, type(exc).__name__)
    return key


# ---------------------------------------------------------------------------
# Public exception (RNF-04 — explicit infrastructure vs functional distinction)
# ---------------------------------------------------------------------------


class InfrastructureError(Exception):
    """Raised on Playwright-level failures: network timeouts, DNS errors, browser crashes.

    Distinct from functional flow failures (e.g. payment rejected by the app).
    The runner catches this and converts it to ``ProfileResult(status="error")``.
    """


# The closed-catalog registry is the single source of truth in ``flow_catalog`` and
# imported above (invariant #2: dispatch via lookup, NEVER if/else on flow name).
# Re-exported here so existing callers ``from src.executor.runner import FLOW_REGISTRY``
# keep working.


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _create_context(
    browser: Browser,
    profile: BrowserProfile,
    env: ResolvedEnvironment,
) -> BrowserContext:
    """Create a browser context configured for ``profile``.

    HTTP basic auth credentials from ``env.env_access`` are injected here so
    that flow code never handles raw credentials (ADR-001). Credentials are NOT
    logged.
    """
    context = await browser.new_context(
        viewport={"width": profile.viewport_width, "height": profile.viewport_height},
        locale=profile.locale,
        user_agent=profile.user_agent,
        is_mobile=profile.is_mobile,
        http_credentials={
            "username": env.env_access.username,
            "password": env.env_access.password,
        },
    )
    return context


async def _take_screenshot(page: Page, path: str) -> None:
    """Capture a screenshot to ``path`` (S3 key / local path).

    Errors are swallowed — a screenshot failure must never abort a run.
    """
    try:
        await page.screenshot(path=path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Screenshot failed (%s): %s", path, type(exc).__name__)


async def _execute_step(
    page: Page,
    step_name: str,
    coro: Coroutine[Any, Any, StepResult],
) -> StepResult:
    """Execute a step coroutine and return the ``StepResult``.

    This thin wrapper exists so future cross-cutting concerns (metrics,
    tracing) can be added in one place without touching each flow.
    """
    return await coro


def _error_flow_result(flow_name: str, error_msg: str) -> FlowResult:
    """Build a minimal ``FlowResult`` for an infrastructure-level error."""
    return FlowResult(
        flow_name=flow_name,  # type: ignore[arg-type]
        status="error",
        steps=[
            StepResult(
                name="infrastructure_error",
                status="failed",
                duration_ms=0,
                error=error_msg,
                screenshot_state="fail",
            )
        ],
        duration_ms=0,
        orders_created=0,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_profile(
    profile: BrowserProfile,
    flow_name: FlowName,
    config: SyntheticUserConfig,
    env: ResolvedEnvironment,
    run_id: str,
) -> ProfileResult:
    """Execute ``flow_name`` in a Playwright browser configured as ``profile``.

    Args:
        profile:   Browser profile (viewport, locale, UA, mobile flag).
        flow_name: One of the closed catalog flow names (invariant #2).
        config:    Validated ``SyntheticUserConfig`` from the API gate.
        env:       Server-side resolved environment with credentials (ADR-001).
        run_id:    Unique run identifier used for evidence naming (ADR-003).

    Returns:
        ``ProfileResult`` with the flow outcome. ``traffic_light`` defaults to
        ``GREEN`` here; the reporter (U3) overwrites it with the p95 verdict.

    Raises:
        KeyError: if ``flow_name`` is not in the FLOW_REGISTRY (programming error).
    """
    flow_fn = FLOW_REGISTRY[flow_name]

    flow_result: FlowResult
    network_summary: NetworkSummary | None = None

    try:
        async with async_playwright() as playwright:
            browser: Browser = await playwright.chromium.launch(headless=True)
            try:
                context = await _create_context(browser, profile, env)
                page = await context.new_page()
                capture = NetworkCapture(env.store_url)
                capture.install(page)
                flow_result = await flow_fn(page, config, env, run_id, profile.name)
                network_summary = await _build_network_summary(
                    page, capture, run_id, profile.name, flow_name
                )
            except PlaywrightError as exc:
                logger.error(
                    "InfrastructureError in flow '%s' profile='%s': %s",
                    flow_name,
                    profile.name,
                    type(exc).__name__,
                )
                raise InfrastructureError(str(exc)) from exc
            finally:
                await browser.close()

    except InfrastructureError as infra_exc:
        flow_result = _error_flow_result(flow_name, str(infra_exc))

    # Hard invariant #1 — NEVER relaxed.
    assert flow_result.orders_created == 0, (
        f"Zero-contamination violated in run_profile: "
        f"orders_created={flow_result.orders_created}"
    )

    profile_result = ProfileResult(
        profile=profile,
        flow_result=flow_result,
        # Placeholder: the reporter (U3) computes the real verdict from p95 baseline.
        traffic_light=TrafficLight.GREEN,
        network_summary=network_summary,
    )

    logger.info(
        "run_profile complete flow='%s' profile='%s' status='%s'",
        flow_name,
        profile.name,
        flow_result.status,
    )
    return profile_result


def _skipped_flow_result(flow_name: str, reason: str) -> FlowResult:
    """A ``FlowResult`` for a composition link skipped after an upstream failure."""
    return FlowResult(
        flow_name=flow_name,  # type: ignore[arg-type]
        status="failed",
        steps=[
            StepResult(name="skipped", status="skipped", duration_ms=0, error=reason)
        ],
        duration_ms=0,
        orders_created=0,
    )


async def run_composition(
    profile: BrowserProfile,
    flow_names: list[FlowName],
    config: SyntheticUserConfig,
    env: ResolvedEnvironment,
    run_id: str,
) -> list[ProfileResult]:
    """Run ``flow_names`` as a chained composition in ONE shared browser context.

    Each flow self-prepares its page; the session (cookies/auth) persists across
    flows. A broken link marks all subsequent flows ``skipped`` (H6.3 AC3). Returns
    one ``ProfileResult`` per flow. ``traffic_light`` is a placeholder — the reporter
    (U3) computes the real verdict.
    """
    results: list[ProfileResult] = []
    try:
        async with async_playwright() as playwright:
            browser: Browser = await playwright.chromium.launch(headless=True)
            try:
                context = await _create_context(browser, profile, env)
                page = await context.new_page()
                capture = NetworkCapture(env.store_url)
                capture.install(page)
                broken = False
                for flow_name in flow_names:
                    if broken:
                        results.append(
                            ProfileResult(
                                profile=profile,
                                flow_result=_skipped_flow_result(
                                    flow_name, "upstream flow in the journey failed"
                                ),
                                traffic_light=TrafficLight.GREEN,
                            )
                        )
                        continue
                    capture.reset()  # segment the capture per flow
                    flow_result = await FLOW_REGISTRY[flow_name](
                        page, config, env, run_id, profile.name
                    )
                    assert flow_result.orders_created == 0, (
                        "Zero-contamination violated in run_composition: "
                        f"orders_created={flow_result.orders_created}"
                    )
                    network_summary = await _build_network_summary(
                        page, capture, run_id, profile.name, flow_name
                    )
                    results.append(
                        ProfileResult(
                            profile=profile,
                            flow_result=flow_result,
                            traffic_light=TrafficLight.GREEN,
                            network_summary=network_summary,
                        )
                    )
                    if flow_result.status != "success":
                        broken = True  # remaining links are skipped
            except PlaywrightError as exc:
                logger.error(
                    "InfrastructureError in composition profile='%s': %s",
                    profile.name,
                    type(exc).__name__,
                )
                raise InfrastructureError(str(exc)) from exc
            finally:
                await browser.close()
    except InfrastructureError as infra_exc:
        for flow_name in flow_names[len(results):]:
            results.append(
                ProfileResult(
                    profile=profile,
                    flow_result=_error_flow_result(flow_name, str(infra_exc)),
                    traffic_light=TrafficLight.YELLOW,
                )
            )
    return results
