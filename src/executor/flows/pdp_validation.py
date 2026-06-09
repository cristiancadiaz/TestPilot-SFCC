"""Flow: pdp_validation — validate the product detail page (U5).

Steps: env_access_auth → search_product (setup) → open_product (setup) →
pdp_price_visible → pdp_variant_selector → pdp_gallery_loads →
pdp_add_to_cart_enabled. No payment (journey flow, C3). ``setup()`` = search +
open the product so the flow lands on a PDP.

Selectors in ``SFCCSelectors``; ADR-003 evidence; ``orders_created`` = 0.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from src.executor.flows._common import (
    execute_flow,
    screenshot_path,
    step_env_access,
    step_open_first_result,
    step_search,
)
from src.executor.selectors import SFCCSelectors
from src.models import FlowResult, ResolvedEnvironment, StepResult, SyntheticUserConfig

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

FLOW_NAME = "pdp_validation"


async def _present(page: "Page", name: str, selector: str) -> StepResult:
    start = time.monotonic()
    try:
        await page.wait_for_selector(selector)
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


async def _add_to_cart_enabled(
    page: "Page", run_id: str, profile_id: str
) -> StepResult:
    """Terminal step — the add-to-cart button is present and enabled (final capture)."""
    name = "pdp_add_to_cart_enabled"
    start = time.monotonic()
    final = screenshot_path(run_id, profile_id, FLOW_NAME, name, "final")
    try:
        button = page.locator(SFCCSelectors.PDP_ADD_TO_CART)
        await button.wait_for()
        if await button.is_disabled():
            raise RuntimeError("add-to-cart button is disabled")
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
    """Run pdp_validation. Setup (search + open) self-prepares the PDP."""
    logger.info("Starting flow '%s' run_id=%s profile=%s", FLOW_NAME, run_id, profile_id)
    search_term = config.products[0].search_term

    return await execute_flow(
        "pdp_validation",
        [
            ("env_access_auth", lambda: step_env_access(page, env)),
            ("search_product", lambda: step_search(page, search_term, phase="setup")),
            ("open_product", lambda: step_open_first_result(page, phase="setup")),
            ("pdp_price_visible", lambda: _present(page, "pdp_price_visible", SFCCSelectors.PDP_PRICE)),
            ("pdp_variant_selector", lambda: _present(page, "pdp_variant_selector", SFCCSelectors.PDP_VARIANT_SELECT)),
            ("pdp_gallery_loads", lambda: _present(page, "pdp_gallery_loads", SFCCSelectors.PDP_GALLERY)),
            ("pdp_add_to_cart_enabled", lambda: _add_to_cart_enabled(page, run_id, profile_id)),
        ],
    )
