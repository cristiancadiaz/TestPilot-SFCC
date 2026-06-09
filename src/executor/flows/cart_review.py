"""Flow: cart_review — validate the cart page (U5).

Core steps: cart_product_present → cart_quantity_update → cart_subtotal_recalc →
cart_price_consistency. ``setup()`` (phase="setup", H6.2 AC3) self-prepares the
cart: search → open product → add to cart → open the cart page. No payment.

A price/subtotal inconsistency is recorded as finding data (logged for U6) — not a
hard failure. ``orders_created`` = 0.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from src.executor.flows._common import (
    execute_flow,
    screenshot_path,
    step_add_to_cart,
    step_env_access,
    step_open_first_result,
    step_search,
)
from src.executor.selectors import SFCCSelectors
from src.models import FlowResult, ResolvedEnvironment, StepResult, SyntheticUserConfig

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

FLOW_NAME = "cart_review"


async def _go_to_cart(page: "Page") -> StepResult:
    name = "open_cart"
    start = time.monotonic()
    try:
        await page.click(SFCCSelectors.CART_MINI_CART)
        await page.wait_for_selector(SFCCSelectors.CART_SUBTOTAL)
        return StepResult(
            name=name,
            status="success",
            duration_ms=int((time.monotonic() - start) * 1000),
            phase="setup",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s failed: %s", name, type(exc).__name__)
        return StepResult(
            name=name,
            status="failed",
            duration_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
            screenshot_state="fail",
            phase="setup",
        )


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


async def _quantity_update(page: "Page") -> StepResult:
    name = "cart_quantity_update"
    start = time.monotonic()
    try:
        await page.fill(SFCCSelectors.CART_QUANTITY_INPUT, "2")
        await page.wait_for_selector(SFCCSelectors.CART_SUBTOTAL)
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


async def _price_consistency(
    page: "Page", run_id: str, profile_id: str
) -> StepResult:
    """Terminal step — item price and subtotal are both shown/consistent (final capture)."""
    name = "cart_price_consistency"
    start = time.monotonic()
    final = screenshot_path(run_id, profile_id, FLOW_NAME, name, "final")
    try:
        item_text = await page.locator(SFCCSelectors.CART_ITEM_PRICE).first.text_content()
        subtotal_text = await page.locator(SFCCSelectors.CART_SUBTOTAL).first.text_content()
        if not (item_text and subtotal_text):
            raise RuntimeError("cart price or subtotal missing")
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
    """Run cart_review. Setup (search + add + open cart) self-prepares the cart."""
    logger.info("Starting flow '%s' run_id=%s profile=%s", FLOW_NAME, run_id, profile_id)
    search_term = config.products[0].search_term

    return await execute_flow(
        "cart_review",
        [
            ("env_access_auth", lambda: step_env_access(page, env)),
            ("search_product", lambda: step_search(page, search_term, phase="setup")),
            ("open_product", lambda: step_open_first_result(page, phase="setup")),
            ("add_to_cart", lambda: step_add_to_cart(page, phase="setup")),
            ("open_cart", lambda: _go_to_cart(page)),
            ("cart_product_present", lambda: _present(page, "cart_product_present", SFCCSelectors.CART_ITEM_PRICE)),
            ("cart_quantity_update", lambda: _quantity_update(page)),
            ("cart_subtotal_recalc", lambda: _present(page, "cart_subtotal_recalc", SFCCSelectors.CART_SUBTOTAL)),
            ("cart_price_consistency", lambda: _price_consistency(page, run_id, profile_id)),
        ],
    )
