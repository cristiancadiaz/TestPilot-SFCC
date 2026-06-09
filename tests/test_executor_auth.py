"""Tests for src/executor/auth/shopper_login.py.

All Playwright ``Page`` interactions are mocked — no real browser is launched.
Covers:
  - Successful login (no error message visible).
  - Failed login (error message visible).
  - Credentials NOT appearing in log output (RNF-03).
  - Selectors sourced from SFCCSelectors (not hardcoded strings).
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.executor.auth.shopper_login import shopper_login
from src.executor.selectors import SFCCSelectors


def _make_page(error_visible: bool = False) -> MagicMock:
    """Build a minimal mock of ``playwright.async_api.Page``.

    Args:
        error_visible: When ``True``, the login error locator returns
                       ``is_visible() == True``, simulating a failed login.
    """
    page = MagicMock()

    # wait_for_selector, fill, click are async operations.
    page.wait_for_selector = AsyncMock(return_value=None)
    page.fill = AsyncMock(return_value=None)
    page.click = AsyncMock(return_value=None)
    page.wait_for_load_state = AsyncMock(return_value=None)

    # locator() returns a locator mock whose is_visible() is async.
    locator_mock = MagicMock()
    locator_mock.is_visible = AsyncMock(return_value=error_visible)
    page.locator = MagicMock(return_value=locator_mock)

    return page


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shopper_login_success() -> None:
    """No error message visible -> StepResult.status == 'success'."""
    page = _make_page(error_visible=False)

    result = await shopper_login(page, "testuser@testpilot.internal", "secret123")

    assert result.status == "success"
    assert result.name == "shopper_login"
    assert result.error is None
    assert result.screenshot_state is None


@pytest.mark.asyncio
async def test_shopper_login_failure() -> None:
    """Error message visible -> StepResult.status == 'failed' and screenshot_state == 'fail'."""
    page = _make_page(error_visible=True)

    result = await shopper_login(page, "testuser@testpilot.internal", "wrongpass")

    assert result.status == "failed"
    assert result.screenshot_state == "fail"
    assert result.error is not None


@pytest.mark.asyncio
async def test_credentials_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Username and password must NOT appear in any log record (RNF-03)."""
    page = _make_page(error_visible=False)
    username = "testuser@example.com"
    password = "secret123"

    with caplog.at_level(logging.DEBUG, logger="src.executor.auth.shopper_login"):
        await shopper_login(page, username, password)

    all_log_text = " ".join(record.getMessage() for record in caplog.records)
    assert username not in all_log_text, "Username leaked into logs"
    assert password not in all_log_text, "Password leaked into logs"


@pytest.mark.asyncio
async def test_uses_selectors_from_selectors_py() -> None:
    """shopper_login must use SFCCSelectors constants, not hardcoded strings."""
    page = _make_page(error_visible=False)

    await shopper_login(page, "testuser@testpilot.internal", "secret123")

    # wait_for_selector should have been called with the selector from SFCCSelectors.
    call_args = [call.args[0] for call in page.wait_for_selector.call_args_list]
    assert SFCCSelectors.LOGIN_EMAIL_INPUT in call_args, (
        f"Expected '{SFCCSelectors.LOGIN_EMAIL_INPUT}' in wait_for_selector calls; "
        f"got: {call_args}"
    )

    # fill should have been called with the email selector.
    fill_selectors = [call.args[0] for call in page.fill.call_args_list]
    assert SFCCSelectors.LOGIN_EMAIL_INPUT in fill_selectors, (
        f"Expected '{SFCCSelectors.LOGIN_EMAIL_INPUT}' in fill calls; got: {fill_selectors}"
    )

    # locator should have been called with the error selector.
    locator_calls = [call.args[0] for call in page.locator.call_args_list]
    assert SFCCSelectors.LOGIN_ERROR_MESSAGE in locator_calls, (
        f"Expected '{SFCCSelectors.LOGIN_ERROR_MESSAGE}' in locator calls; "
        f"got: {locator_calls}"
    )


@pytest.mark.asyncio
async def test_shopper_login_exception_returns_failed() -> None:
    """An unexpected exception during login returns status='failed'."""
    page = MagicMock()
    page.wait_for_selector = AsyncMock(side_effect=RuntimeError("unexpected"))

    result = await shopper_login(page, "testuser@testpilot.internal", "secret123")

    assert result.status == "failed"
    assert result.screenshot_state == "fail"
    assert result.error is not None
