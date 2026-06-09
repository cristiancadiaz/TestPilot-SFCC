"""Flow: browse_discounted_products — offers PLP → discounted PDP (U5).

Steps: env_access_auth → navigate_to_promotions → plp_discount_display_validation
→ select_discounted_product → pdp_discount_consistency. No payment (journey flow).

A price/discount inconsistency between the PLP and PDP is recorded as **finding
data** (logged for the U6 collectors) — it is NOT a hard failure (H6.4 AC3): the
deterministic verdict belongs to the baseline, and audit findings belong to U6.
``orders_created`` = 0.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from src.executor.flows._common import (
    execute_flow,
    screenshot_path,
    step_env_access,
)
from src.executor.selectors import SFCCSelectors
from src.models import FlowResult, ResolvedEnvironment, StepResult, SyntheticUserConfig

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

FLOW_NAME = "browse_discounted_products"


async def _navigate_to_promotions(page: "Page") -> StepResult:
    name = "navigate_to_promotions"
    start = time.monotonic()
    try:
        await page.click(SFCCSelectors.PROMOTIONS_NAV)
        await page.wait_for_selector(SFCCSelectors.SEARCH_RESULTS_GRID)
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


async def _plp_discount_display(page: "Page") -> StepResult:
    """Original (struck) price + discounted price are both shown on the offers PLP."""
    name = "plp_discount_display_validation"
    start = time.monotonic()
    try:
        await page.wait_for_selector(SFCCSelectors.PROMOTIONS_ORIGINAL_PRICE)
        await page.wait_for_selector(SFCCSelectors.PROMOTIONS_DISCOUNTED_PRICE)
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


async def _select_discounted_product(page: "Page", observed: dict[str, str]) -> StepResult:
    """Capture the PLP discounted price, then open the product's PDP."""
    name = "select_discounted_product"
    start = time.monotonic()
    try:
        price_text = await page.locator(
            SFCCSelectors.PROMOTIONS_DISCOUNTED_PRICE
        ).first.text_content()
        observed["plp_price"] = (price_text or "").strip()
        tile = page.locator(SFCCSelectors.PLP_TILE_LINK).first
        await tile.wait_for()
        await tile.click()
        await page.wait_for_selector(SFCCSelectors.PDP_PRODUCT_NAME)
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


async def _pdp_discount_consistency(
    page: "Page", observed: dict[str, str], run_id: str, profile_id: str
) -> StepResult:
    """Terminal step — PDP price matches the PLP discounted price (finding if not)."""
    name = "pdp_discount_consistency"
    start = time.monotonic()
    final = screenshot_path(run_id, profile_id, FLOW_NAME, name, "final")
    try:
        pdp_text = await page.locator(SFCCSelectors.PDP_PRICE).first.text_content()
        pdp_price = (pdp_text or "").strip()
        plp_price = observed.get("plp_price", "")
        if plp_price and pdp_price and plp_price != pdp_price:
            # Finding data for U6 — NOT a hard failure (H6.4 AC3).
            logger.info(
                "discount inconsistency finding: plp=%s pdp=%s", plp_price, pdp_price
            )
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
    """Run browse_discounted_products."""
    logger.info("Starting flow '%s' run_id=%s profile=%s", FLOW_NAME, run_id, profile_id)
    observed: dict[str, str] = {}

    return await execute_flow(
        "browse_discounted_products",
        [
            ("env_access_auth", lambda: step_env_access(page, env)),
            ("navigate_to_promotions", lambda: _navigate_to_promotions(page)),
            ("plp_discount_display_validation", lambda: _plp_discount_display(page)),
            ("select_discounted_product", lambda: _select_discounted_product(page, observed)),
            ("pdp_discount_consistency", lambda: _pdp_discount_consistency(page, observed, run_id, profile_id)),
        ],
    )
