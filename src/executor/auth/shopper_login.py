"""Shopper login helper for SFCC SFRA storefronts.

Encapsulates the login form interaction. Credentials arrive as plain
strings already resolved from ``ResolvedEnvironment.shopper`` by the
caller — this module NEVER accesses Secrets Manager or env variables
directly (ADR-001).

Security: username and password are NEVER written to logs (RNF-03).
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from src.executor.selectors import SFCCSelectors
from src.models import StepResult

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def shopper_login(page: "Page", username: str, password: str) -> StepResult:
    """Log in a synthetic shopper via the SFRA login form.

    Args:
        page:     Active Playwright ``Page`` already navigated to a page
                  that can surface the login form.
        username: Shopper email address (always ``@testpilot.internal``).
        password: Shopper password (resolved server-side, never logged).

    Returns:
        ``StepResult`` with ``status="success"`` if login succeeds, or
        ``status="failed"`` (with ``screenshot_state="fail"``) if the
        storefront surfaces a login error message.
    """
    step_name = "shopper_login"
    start = time.monotonic()

    # Credentials are intentionally NOT included in any log statement.
    logger.debug("Starting shopper_login step")

    try:
        # Fill login form fields — selectors from the central registry only.
        await page.wait_for_selector(SFCCSelectors.LOGIN_EMAIL_INPUT)
        await page.fill(SFCCSelectors.LOGIN_EMAIL_INPUT, username)
        await page.fill(SFCCSelectors.LOGIN_PASSWORD_INPUT, password)
        await page.click(SFCCSelectors.LOGIN_SUBMIT_BUTTON)

        # Wait for the page to react — either an error banner or a
        # post-login element (e.g., account page) becomes visible.
        # We wait for either condition to appear.
        error_locator = page.locator(SFCCSelectors.LOGIN_ERROR_MESSAGE)
        await page.wait_for_load_state("networkidle")

        duration_ms = int((time.monotonic() - start) * 1000)

        if await error_locator.is_visible():
            logger.warning("shopper_login: login error message detected")
            return StepResult(
                name=step_name,
                status="failed",
                duration_ms=duration_ms,
                error="Login error message visible after submit",
                screenshot_state="fail",
            )

        logger.debug("shopper_login: completed successfully")
        return StepResult(
            name=step_name,
            status="success",
            duration_ms=duration_ms,
        )

    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.warning("shopper_login: unexpected exception — %s", type(exc).__name__)
        return StepResult(
            name=step_name,
            status="failed",
            duration_ms=duration_ms,
            error=str(exc),
            screenshot_state="fail",
        )
