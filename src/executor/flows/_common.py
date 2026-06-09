"""Shared helpers for the U5 journey flows.

Keeps the journey flow modules lean: a step is an ``async`` callable returning a
``StepResult``; ``execute_flow`` runs them in order, marks everything after a
failure as ``skipped`` (preserving each step's ``phase``), and assembles the
``FlowResult`` (``orders_created`` is ALWAYS 0 — journey flows never touch payment).

Evidence (ADR-003): the terminal step sets ``screenshot_state="final"`` on success
and a failing step sets ``"fail"`` — done inside the step coroutines themselves.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from src.executor.selectors import SFCCSelectors
from src.models import FlowName, FlowResult, ResolvedEnvironment, StepResult

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

StepFn = Callable[[], Awaitable[StepResult]]


async def _timed(name: str, action: Callable[[], Awaitable[None]], *, phase: str = "flow") -> StepResult:
    """Run *action*, returning a timed StepResult (failed+fail-screenshot on error)."""
    start = time.monotonic()
    try:
        await action()
        return StepResult(
            name=name,
            status="success",
            duration_ms=int((time.monotonic() - start) * 1000),
            phase=phase,  # type: ignore[arg-type]
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s failed: %s", name, type(exc).__name__)
        return StepResult(
            name=name,
            status="failed",
            duration_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
            screenshot_state="fail",
            phase=phase,  # type: ignore[arg-type]
        )


async def step_env_access(page: "Page", env: ResolvedEnvironment) -> StepResult:
    """Navigate to the storefront (HTTP basic auth is set on the context, ADR-001)."""

    async def _do() -> None:
        await page.goto(env.store_url)
        await page.wait_for_load_state("networkidle")

    return await _timed("env_access_auth", _do)


async def step_search(page: "Page", search_term: str, *, phase: str = "flow") -> StepResult:
    """Search from the header and wait for the results grid."""

    async def _do() -> None:
        await page.wait_for_selector(SFCCSelectors.SEARCH_INPUT)
        await page.fill(SFCCSelectors.SEARCH_INPUT, search_term)
        await page.click(SFCCSelectors.SEARCH_SUBMIT)
        await page.wait_for_selector(SFCCSelectors.SEARCH_RESULTS_GRID)

    return await _timed("search_product", _do, phase=phase)


async def step_open_first_result(page: "Page", *, phase: str = "flow") -> StepResult:
    """Open the first PLP grid tile and wait for the PDP."""

    async def _do() -> None:
        first = page.locator(SFCCSelectors.SEARCH_RESULTS_GRID).first
        await first.wait_for()
        await first.click()
        await page.wait_for_selector(SFCCSelectors.PDP_PRODUCT_NAME)

    return await _timed("open_product", _do, phase=phase)


async def step_add_to_cart(page: "Page", *, phase: str = "flow") -> StepResult:
    """Add the current PDP product to the cart and wait for the mini-cart."""

    async def _do() -> None:
        await page.wait_for_selector(SFCCSelectors.PDP_ADD_TO_CART)
        await page.click(SFCCSelectors.PDP_ADD_TO_CART)
        await page.wait_for_selector(SFCCSelectors.CART_MINI_CART)

    return await _timed("add_to_cart", _do, phase=phase)


def skipped(name: str, *, phase: str = "flow") -> StepResult:
    """Return a ``skipped`` StepResult for a step not executed."""
    return StepResult(name=name, status="skipped", duration_ms=0, phase=phase)  # type: ignore[arg-type]


def screenshot_path(
    run_id: str, profile_id: str, flow_name: str, step_name: str, state: str
) -> str:
    """ADR-003 evidence path: ``{run_id}/{profile}/{flow}/{step}-{state}.png``."""
    return f"{run_id}/{profile_id}/{flow_name}/{step_name}-{state}.png"


async def execute_flow(
    flow_name: FlowName,
    ordered_steps: list[tuple[str, StepFn]],
) -> FlowResult:
    """Run ``ordered_steps`` sequentially; mark steps after a failure as skipped."""
    flow_start = time.monotonic()
    steps: list[StepResult] = []
    failed = False
    for name, fn in ordered_steps:
        if failed:
            steps.append(StepResult(name=name, status="skipped", duration_ms=0))
            continue
        result = await fn()
        if result.status == "failed":
            failed = True
        steps.append(result)
    status: str = "success" if all(s.status == "success" for s in steps) else "failed"
    duration_ms = int((time.monotonic() - flow_start) * 1000)
    return FlowResult(
        flow_name=flow_name,
        status=status,  # type: ignore[arg-type]
        steps=steps,
        duration_ms=duration_ms,
        orders_created=0,
    )
