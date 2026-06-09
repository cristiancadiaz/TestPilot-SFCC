"""Flow: search_and_filter — header search → PLP → refine → validate grid (U5).

Steps: env_access_auth → search_from_header → plp_results_validation →
apply_refinement → grid_response_validation. No payment, ever (journey flow, C3).
``setup()`` is a no-op (no prior state required).

Selectors live in ``SFCCSelectors``; waits via ``wait_for_selector`` (never
``time.sleep``). Evidence per ADR-003 (fail + final). ``orders_created`` is 0.
Observed prices are logged for the U6 audit collectors (no model field yet).
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from src.executor.flows._common import (
    execute_flow,
    screenshot_path,
    step_env_access,
    step_search,
)
from src.executor.selectors import SFCCSelectors
from src.models import FlowResult, ResolvedEnvironment, StepResult, SyntheticUserConfig

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

FLOW_NAME = "search_and_filter"


async def _plp_results_validation(page: "Page") -> StepResult:
    name = "plp_results_validation"
    start = time.monotonic()
    try:
        await page.wait_for_selector(SFCCSelectors.SEARCH_RESULTS_GRID)
        await page.wait_for_selector(SFCCSelectors.PLP_RESULT_COUNT)
        return StepResult(
            name=name, status="success", duration_ms=int((time.monotonic() - start) * 1000)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s failed: %s", name, type(exc).__name__)
        return StepResult(
            name=name,
            status="failed",
            duration_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
            screenshot_state="fail",
        )


async def _apply_refinement(page: "Page") -> StepResult:
    name = "apply_refinement"
    start = time.monotonic()
    try:
        refinement = page.locator(SFCCSelectors.PLP_REFINEMENT_CATEGORY).first
        await refinement.wait_for()
        await refinement.click()
        await page.wait_for_selector(SFCCSelectors.PLP_APPLIED_REFINEMENT)
        return StepResult(
            name=name, status="success", duration_ms=int((time.monotonic() - start) * 1000)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s failed: %s", name, type(exc).__name__)
        return StepResult(
            name=name,
            status="failed",
            duration_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
            screenshot_state="fail",
        )


async def _grid_response_validation(
    page: "Page", run_id: str, profile_id: str
) -> StepResult:
    """Terminal step — grid still renders after refinement (ADR-003 final capture)."""
    name = "grid_response_validation"
    start = time.monotonic()
    final = screenshot_path(run_id, profile_id, FLOW_NAME, name, "final")
    try:
        await page.wait_for_selector(SFCCSelectors.SEARCH_RESULTS_GRID)
        return StepResult(
            name=name,
            status="success",
            duration_ms=int((time.monotonic() - start) * 1000),
            screenshot_url=final,
            screenshot_state="final",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s failed: %s", name, type(exc).__name__)
        return StepResult(
            name=name,
            status="failed",
            duration_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
            screenshot_url=screenshot_path(run_id, profile_id, FLOW_NAME, name, "fail"),
            screenshot_state="fail",
        )


async def run(
    page: "Page",
    config: SyntheticUserConfig,
    env: ResolvedEnvironment,
    run_id: str,
    profile_id: str,
) -> FlowResult:
    """Run search_and_filter (env-access → search → PLP → refine → validate grid)."""
    logger.info("Starting flow '%s' run_id=%s profile=%s", FLOW_NAME, run_id, profile_id)
    search_term = config.products[0].search_term

    return await execute_flow(
        "search_and_filter",
        [
            ("env_access_auth", lambda: step_env_access(page, env)),
            ("search_from_header", lambda: step_search(page, search_term)),
            ("plp_results_validation", lambda: _plp_results_validation(page)),
            ("apply_refinement", lambda: _apply_refinement(page)),
            ("grid_response_validation", lambda: _grid_response_validation(page, run_id, profile_id)),
        ],
    )
