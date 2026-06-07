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

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
)
from playwright.async_api import Error as PlaywrightError

from src.executor.flows import checkout_card_declined, checkout_full
from src.models import (
    BrowserProfile,
    FlowName,
    FlowResult,
    ProfileResult,
    ResolvedEnvironment,
    StepResult,
    SyntheticUserConfig,
    TrafficLight,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public exception (RNF-04 — explicit infrastructure vs functional distinction)
# ---------------------------------------------------------------------------


class InfrastructureError(Exception):
    """Raised on Playwright-level failures: network timeouts, DNS errors, browser crashes.

    Distinct from functional flow failures (e.g. payment rejected by the app).
    The runner catches this and converts it to ``ProfileResult(status="error")``.
    """


# ---------------------------------------------------------------------------
# Flow registry — dispatch table (invariant #2: NO if/else on flow name)
# ---------------------------------------------------------------------------

# Each entry maps a FlowName to the coroutine function exposed by the flow module.
_FlowCoro = Callable[
    [Page, SyntheticUserConfig, ResolvedEnvironment, str, str],
    Coroutine[Any, Any, FlowResult],
]

FLOW_REGISTRY: dict[str, _FlowCoro] = {
    "checkout_full": checkout_full.run,
    "checkout_card_declined": checkout_card_declined.run,
}
"""Closed catalog registry for wave-1 flows. Add entries here (not if/else)."""


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

    try:
        async with async_playwright() as playwright:
            browser: Browser = await playwright.chromium.launch(headless=True)
            try:
                context = await _create_context(browser, profile, env)
                page = await context.new_page()
                flow_result = await flow_fn(page, config, env, run_id, profile.name)
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
    )

    logger.info(
        "run_profile complete flow='%s' profile='%s' status='%s'",
        flow_name,
        profile.name,
        flow_result.status,
    )
    return profile_result
