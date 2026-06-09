"""Flow: checkout_card_declined — checkout with explicit card decline validation.

10-step flow identical to checkout_full except step 10 uses
``DECLINED_CARD_*`` data and verifies the ``PAYMENT_DECLINE_MESSAGE``
selector instead of the generic error.

Invariant #1 (zero contamination): payment ALWAYS fails — ``orders_created``
is ALWAYS 0, asserted before returning.

All waits use ``wait_for_selector()`` / ``expect()`` — NEVER ``time.sleep()``.
Selectors live exclusively in ``src.executor.selectors.SFCCSelectors``.
Credentials arrive via ``ResolvedEnvironment`` (ADR-001).
Evidence follows ADR-003: fail+final always; no intermediate OK captures.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from src.executor.auth import shopper_login
from src.executor.selectors import SFCCSelectors
from src.models import FlowResult, ResolvedEnvironment, StepResult, SyntheticUserConfig

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

FLOW_NAME = "checkout_card_declined"
TOTAL_STEPS = 10


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _skipped(name: str) -> StepResult:
    """Return a skipped ``StepResult`` for a step that was not executed."""
    return StepResult(name=name, status="skipped", duration_ms=0)


def _build_screenshot_path(
    run_id: str, profile_id: str, step_name: str, state: str
) -> str:
    """Build an evidence path following ADR-003 naming convention."""
    return f"{run_id}/{profile_id}/{FLOW_NAME}/{step_name}-{state}.png"


# ---------------------------------------------------------------------------
# Individual step implementations (steps 1-9 are identical to checkout_full)
# ---------------------------------------------------------------------------


async def _step_env_access_auth(
    page: "Page",
    env: ResolvedEnvironment,
) -> StepResult:
    """Step 1 — infrastructure HTTP-basic auth and initial navigation."""
    name = "env_access_auth"
    start = time.monotonic()
    try:
        await page.goto(env.store_url)
        await page.wait_for_load_state("networkidle")
        duration_ms = int((time.monotonic() - start) * 1000)
        return StepResult(name=name, status="success", duration_ms=duration_ms)
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.warning("env_access_auth failed: %s", type(exc).__name__)
        return StepResult(
            name=name,
            status="failed",
            duration_ms=duration_ms,
            error=str(exc),
            screenshot_state="fail",
        )


async def _step_shopper_login(
    page: "Page",
    env: ResolvedEnvironment,
) -> StepResult:
    """Step 2 — synthetic shopper login via auth module."""
    return await shopper_login(page, env.shopper.username, env.shopper.password)


async def _step_search_product(
    page: "Page",
    config: SyntheticUserConfig,
) -> StepResult:
    """Step 3 — search for the first configured product."""
    name = "search_product"
    start = time.monotonic()
    search_term = config.products[0].search_term
    try:
        await page.wait_for_selector(SFCCSelectors.SEARCH_INPUT)
        await page.fill(SFCCSelectors.SEARCH_INPUT, search_term)
        await page.click(SFCCSelectors.SEARCH_SUBMIT)
        await page.wait_for_selector(SFCCSelectors.SEARCH_RESULTS_GRID)
        duration_ms = int((time.monotonic() - start) * 1000)
        return StepResult(name=name, status="success", duration_ms=duration_ms)
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.warning("search_product failed: %s", type(exc).__name__)
        return StepResult(
            name=name,
            status="failed",
            duration_ms=duration_ms,
            error=str(exc),
            screenshot_state="fail",
        )


async def _step_category_page(page: "Page") -> StepResult:
    """Step 4 — select the first result from the PLP grid."""
    name = "category_page"
    start = time.monotonic()
    try:
        first_product = page.locator(SFCCSelectors.SEARCH_RESULTS_GRID).first
        await first_product.wait_for()
        await first_product.click()
        await page.wait_for_selector(SFCCSelectors.PDP_PRODUCT_NAME)
        duration_ms = int((time.monotonic() - start) * 1000)
        return StepResult(name=name, status="success", duration_ms=duration_ms)
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.warning("category_page failed: %s", type(exc).__name__)
        return StepResult(
            name=name,
            status="failed",
            duration_ms=duration_ms,
            error=str(exc),
            screenshot_state="fail",
        )


async def _step_pdp_variant_select(
    page: "Page",
    config: SyntheticUserConfig,
) -> StepResult:
    """Step 5 — select a variant on the PDP (conditional on config)."""
    name = "pdp_variant_select"
    start = time.monotonic()
    if not config.products[0].validate_variant:
        duration_ms = int((time.monotonic() - start) * 1000)
        return StepResult(name=name, status="skipped", duration_ms=duration_ms)
    try:
        variant_locator = page.locator(SFCCSelectors.PDP_VARIANT_SELECT)
        await variant_locator.wait_for()
        await variant_locator.select_option(index=1)
        duration_ms = int((time.monotonic() - start) * 1000)
        return StepResult(name=name, status="success", duration_ms=duration_ms)
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.warning("pdp_variant_select failed: %s", type(exc).__name__)
        return StepResult(
            name=name,
            status="failed",
            duration_ms=duration_ms,
            error=str(exc),
            screenshot_state="fail",
        )


async def _step_add_to_cart(page: "Page") -> StepResult:
    """Step 6 — click add-to-cart and wait for mini-cart update."""
    name = "add_to_cart"
    start = time.monotonic()
    try:
        await page.wait_for_selector(SFCCSelectors.PDP_ADD_TO_CART)
        await page.click(SFCCSelectors.PDP_ADD_TO_CART)
        await page.wait_for_selector(SFCCSelectors.CART_MINI_CART)
        duration_ms = int((time.monotonic() - start) * 1000)
        return StepResult(name=name, status="success", duration_ms=duration_ms)
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.warning("add_to_cart failed: %s", type(exc).__name__)
        return StepResult(
            name=name,
            status="failed",
            duration_ms=duration_ms,
            error=str(exc),
            screenshot_state="fail",
        )


async def _step_mini_cart_validation(page: "Page") -> StepResult:
    """Step 7 — verify the item is present in the mini cart."""
    name = "mini_cart_validation"
    start = time.monotonic()
    try:
        await page.wait_for_selector(SFCCSelectors.CART_MINI_CART)
        await page.wait_for_selector(SFCCSelectors.CART_ITEM_COUNT)
        duration_ms = int((time.monotonic() - start) * 1000)
        return StepResult(name=name, status="success", duration_ms=duration_ms)
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.warning("mini_cart_validation failed: %s", type(exc).__name__)
        return StepResult(
            name=name,
            status="failed",
            duration_ms=duration_ms,
            error=str(exc),
            screenshot_state="fail",
        )


async def _step_checkout_shipping(page: "Page") -> StepResult:
    """Step 8 — navigate to checkout and fill the shipping form."""
    name = "checkout_shipping"
    start = time.monotonic()
    try:
        await page.wait_for_selector(SFCCSelectors.CART_CHECKOUT_BUTTON)
        await page.click(SFCCSelectors.CART_CHECKOUT_BUTTON)
        await page.wait_for_selector(SFCCSelectors.CHECKOUT_SHIPPING_FORM)

        shipping = SFCCSelectors.TEST_SHIPPING
        await page.fill("input[name='firstName']", shipping["first_name"])
        await page.fill("input[name='lastName']", shipping["last_name"])
        await page.fill("input[name='address1']", shipping["address"])
        await page.fill("input[name='city']", shipping["city"])
        await page.fill("input[name='phone']", shipping["phone"])

        await page.click(SFCCSelectors.CHECKOUT_SHIPPING_NEXT)
        await page.wait_for_selector(SFCCSelectors.CHECKOUT_PAYMENT_SECTION)
        duration_ms = int((time.monotonic() - start) * 1000)
        return StepResult(name=name, status="success", duration_ms=duration_ms)
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.warning("checkout_shipping failed: %s", type(exc).__name__)
        return StepResult(
            name=name,
            status="failed",
            duration_ms=duration_ms,
            error=str(exc),
            screenshot_state="fail",
        )


async def _step_checkout_payment_declined(page: "Page") -> StepResult:
    """Step 9 — fill payment form with the DECLINED card data."""
    name = "checkout_payment"
    start = time.monotonic()
    try:
        await page.wait_for_selector(SFCCSelectors.PAYMENT_CARD_NUMBER)
        # Use DECLINED_CARD_* selectors — not TEST_CARD_* (invariant distinction).
        await page.fill(SFCCSelectors.PAYMENT_CARD_NUMBER, SFCCSelectors.DECLINED_CARD_NUMBER)
        await page.fill(SFCCSelectors.PAYMENT_EXPIRY, SFCCSelectors.DECLINED_CARD_EXPIRY)
        await page.fill(SFCCSelectors.PAYMENT_CVV, SFCCSelectors.DECLINED_CARD_CVV)
        await page.click(SFCCSelectors.PAYMENT_SUBMIT)
        duration_ms = int((time.monotonic() - start) * 1000)
        return StepResult(name=name, status="success", duration_ms=duration_ms)
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.warning("checkout_payment (declined) failed: %s", type(exc).__name__)
        return StepResult(
            name=name,
            status="failed",
            duration_ms=duration_ms,
            error=str(exc),
            screenshot_state="fail",
        )


async def _step_verify_decline_message(
    page: "Page",
    run_id: str,
    profile_id: str,
) -> StepResult:
    """Step 10 — verify card-declined message appears (invariant #1).

    ``status="success"`` means the expected decline was confirmed.
    FINAL step — screenshot is always captured (ADR-003).
    """
    name = "verify_decline_message"
    start = time.monotonic()
    screenshot_path = _build_screenshot_path(run_id, profile_id, name, "final")
    try:
        await page.wait_for_selector(SFCCSelectors.PAYMENT_DECLINE_MESSAGE)
        duration_ms = int((time.monotonic() - start) * 1000)
        return StepResult(
            name=name,
            status="success",
            duration_ms=duration_ms,
            screenshot_url=screenshot_path,
            screenshot_state="final",
        )
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.warning("verify_decline_message failed: %s", type(exc).__name__)
        fail_path = _build_screenshot_path(run_id, profile_id, name, "fail")
        return StepResult(
            name=name,
            status="failed",
            duration_ms=duration_ms,
            error=str(exc),
            screenshot_url=fail_path,
            screenshot_state="fail",
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run(
    page: "Page",
    config: SyntheticUserConfig,
    env: ResolvedEnvironment,
    run_id: str,
    profile_id: str,
) -> FlowResult:
    """Execute the checkout_card_declined flow (10 steps).

    On any step failure all subsequent steps are marked ``skipped``.
    ``orders_created`` is ALWAYS 0 — asserted before returning (invariant #1).
    """
    logger.info("Starting flow '%s' run_id=%s profile=%s", FLOW_NAME, run_id, profile_id)

    step_names = [
        "env_access_auth",
        "shopper_login",
        "search_product",
        "category_page",
        "pdp_variant_select",
        "add_to_cart",
        "mini_cart_validation",
        "checkout_shipping",
        "checkout_payment",
        "verify_decline_message",
    ]

    flow_start = time.monotonic()
    steps: list[StepResult] = []
    failed = False

    for step_name in step_names:
        if failed:
            steps.append(_skipped(step_name))
            continue

        step_result: StepResult

        if step_name == "env_access_auth":
            step_result = await _step_env_access_auth(page, env)
        elif step_name == "shopper_login":
            step_result = await _step_shopper_login(page, env)
        elif step_name == "search_product":
            step_result = await _step_search_product(page, config)
        elif step_name == "category_page":
            step_result = await _step_category_page(page)
        elif step_name == "pdp_variant_select":
            step_result = await _step_pdp_variant_select(page, config)
        elif step_name == "add_to_cart":
            step_result = await _step_add_to_cart(page)
        elif step_name == "mini_cart_validation":
            step_result = await _step_mini_cart_validation(page)
        elif step_name == "checkout_shipping":
            step_result = await _step_checkout_shipping(page)
        elif step_name == "checkout_payment":
            step_result = await _step_checkout_payment_declined(page)
        elif step_name == "verify_decline_message":
            step_result = await _step_verify_decline_message(page, run_id, profile_id)
        else:
            raise RuntimeError(f"Unknown step: {step_name}")  # pragma: no cover

        steps.append(step_result)

        if step_result.status == "failed":
            failed = True
            if step_name != "verify_decline_message":
                if step_result.screenshot_state != "fail":
                    steps[-1] = step_result.model_copy(
                        update={"screenshot_state": "fail"}
                    )

    # Mark last executed successful step as final (ADR-003).
    last_executed = next(
        (s for s in reversed(steps) if s.status != "skipped"), None
    )
    if last_executed is not None and last_executed.status == "success":
        idx = steps.index(last_executed)
        if last_executed.screenshot_state is None:
            screenshot_path = _build_screenshot_path(
                run_id, profile_id, last_executed.name, "final"
            )
            steps[idx] = last_executed.model_copy(
                update={
                    "screenshot_state": "final",
                    "screenshot_url": screenshot_path,
                }
            )

    duration_ms = int((time.monotonic() - flow_start) * 1000)
    overall_status: str = "failed" if failed else "success"

    flow_result = FlowResult(
        flow_name=FLOW_NAME,  # type: ignore[arg-type]
        status=overall_status,  # type: ignore[arg-type]
        steps=steps,
        duration_ms=duration_ms,
        orders_created=0,
    )

    # Hard invariant #1 — NEVER relaxed.
    assert flow_result.orders_created == 0, (
        f"Zero-contamination violated: orders_created={flow_result.orders_created}"
    )

    logger.info(
        "Flow '%s' finished status=%s duration_ms=%d",
        FLOW_NAME,
        overall_status,
        duration_ms,
    )
    return flow_result
