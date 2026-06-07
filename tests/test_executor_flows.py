"""Tests for src/executor/flows/checkout_full.py and checkout_card_declined.py.

All Playwright ``Page`` interactions are mocked — no real browser is launched.
Covers:
  - Successful flow execution and return type.
  - orders_created == 0 invariant.
  - 10-step count.
  - Step failure marks remaining steps as 'skipped'.
  - Screenshot policy (ADR-003): final step tagged 'final'; no OK-intermediate captures.
  - checkout_card_declined uses DECLINED_CARD_* selectors.
  - No ``time.sleep`` in flow modules (AST inspection).
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.executor.flows import checkout_card_declined, checkout_full
from src.executor.selectors import SFCCSelectors
from src.models import (
    Credentials,
    FlowResult,
    Product,
    ResolvedEnvironment,
    SyntheticUserConfig,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config() -> SyntheticUserConfig:
    """Minimal SyntheticUserConfig for testing."""
    return SyntheticUserConfig(
        environment_id="staging",
        flows=["checkout_full"],
        profiles=["desktop_co"],
        products=[Product(search_term="shirt", validate_variant=False)],
        mode="gate",
    )


def _make_env() -> ResolvedEnvironment:
    """ResolvedEnvironment with synthetic (non-real) credentials."""
    return ResolvedEnvironment(
        environment_id="staging",
        store_url="https://staging.example.com",
        env_access=Credentials(username="infra_user", password="infra_pass"),
        shopper=Credentials(
            username="shopper@testpilot.internal",
            password="shopperpass",
        ),
    )


def _make_page_success() -> MagicMock:
    """Page mock where all operations succeed and the final error selector IS visible."""
    page = MagicMock()
    page.wait_for_selector = AsyncMock(return_value=None)
    page.wait_for_load_state = AsyncMock(return_value=None)
    page.fill = AsyncMock(return_value=None)
    page.click = AsyncMock(return_value=None)
    page.goto = AsyncMock(return_value=None)
    page.screenshot = AsyncMock(return_value=None)

    # locator() for mini-cart, variant selector, PLP grid first item.
    locator_mock = MagicMock()
    locator_mock.wait_for = AsyncMock(return_value=None)
    locator_mock.click = AsyncMock(return_value=None)
    locator_mock.select_option = AsyncMock(return_value=None)
    locator_mock.is_visible = AsyncMock(return_value=False)  # no login error
    locator_mock.first = locator_mock  # .first returns itself
    page.locator = MagicMock(return_value=locator_mock)

    return page


def _make_page_add_to_cart_fails() -> MagicMock:
    """Page mock where add_to_cart step (step 6) raises an exception."""
    page = _make_page_success()

    async def _wait_for_selector_side_effect(selector: str, **kwargs: object) -> None:
        # Fail on the PDP_ADD_TO_CART selector
        if selector == SFCCSelectors.PDP_ADD_TO_CART:
            raise Exception("element not found")
        return None

    page.wait_for_selector = AsyncMock(side_effect=_wait_for_selector_side_effect)
    return page


# ---------------------------------------------------------------------------
# checkout_full tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkout_full_returns_flow_result() -> None:
    """All steps succeed -> FlowResult with status='success' and correct flow_name."""
    page = _make_page_success()
    config = _make_config()
    env = _make_env()

    result = await checkout_full.run(page, config, env, "run-001", "desktop_co")

    assert isinstance(result, FlowResult)
    assert result.flow_name == "checkout_full"
    assert result.status == "success"


@pytest.mark.asyncio
async def test_checkout_full_orders_created_zero() -> None:
    """orders_created is ALWAYS 0 (zero-contamination invariant #1)."""
    page = _make_page_success()
    config = _make_config()
    env = _make_env()

    result = await checkout_full.run(page, config, env, "run-001", "desktop_co")

    assert result.orders_created == 0


@pytest.mark.asyncio
async def test_checkout_full_has_10_steps() -> None:
    """The flow must produce exactly 10 StepResults."""
    page = _make_page_success()
    config = _make_config()
    env = _make_env()

    result = await checkout_full.run(page, config, env, "run-001", "desktop_co")

    assert len(result.steps) == 10


@pytest.mark.asyncio
async def test_checkout_full_step_failure_marks_remainder_skipped() -> None:
    """When add_to_cart (step 6) fails, steps 7-10 must be 'skipped'."""
    page = _make_page_add_to_cart_fails()
    config = _make_config()
    env = _make_env()

    result = await checkout_full.run(page, config, env, "run-002", "desktop_co")

    step_names = [s.name for s in result.steps]
    add_to_cart_idx = step_names.index("add_to_cart")

    failed_step = result.steps[add_to_cart_idx]
    assert failed_step.status == "failed"

    for step in result.steps[add_to_cart_idx + 1 :]:
        assert step.status == "skipped", (
            f"Expected step '{step.name}' to be skipped, got '{step.status}'"
        )


@pytest.mark.asyncio
async def test_checkout_full_screenshot_policy() -> None:
    """ADR-003: final step has screenshot_state='final'; no clean OK step has a screenshot."""
    page = _make_page_success()
    config = _make_config()
    env = _make_env()

    result = await checkout_full.run(page, config, env, "run-001", "desktop_co")

    # Find the last non-skipped step.
    executed = [s for s in result.steps if s.status != "skipped"]
    last_step = executed[-1]
    assert last_step.screenshot_state == "final", (
        f"Last step '{last_step.name}' screenshot_state should be 'final', "
        f"got '{last_step.screenshot_state}'"
    )

    # All intermediate successful steps (not last) must have screenshot_state=None.
    for step in executed[:-1]:
        assert step.screenshot_state is None, (
            f"Intermediate OK step '{step.name}' should not have a screenshot_state, "
            f"got '{step.screenshot_state}'"
        )


# ---------------------------------------------------------------------------
# checkout_card_declined tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkout_card_declined_returns_flow_result() -> None:
    """verify_decline_message succeeds -> FlowResult with status='success'."""
    page = _make_page_success()
    config = _make_config()
    env = _make_env()

    result = await checkout_card_declined.run(page, config, env, "run-003", "mobile_co")

    assert isinstance(result, FlowResult)
    assert result.flow_name == "checkout_card_declined"
    assert result.status == "success"


@pytest.mark.asyncio
async def test_checkout_card_declined_orders_created_zero() -> None:
    """orders_created is ALWAYS 0 (zero-contamination invariant #1)."""
    page = _make_page_success()
    config = _make_config()
    env = _make_env()

    result = await checkout_card_declined.run(page, config, env, "run-003", "mobile_co")

    assert result.orders_created == 0


@pytest.mark.asyncio
async def test_checkout_card_declined_uses_declined_card() -> None:
    """checkout_payment step must fill DECLINED_CARD_NUMBER, not TEST_CARD_NUMBER."""
    page = _make_page_success()
    config = _make_config()
    env = _make_env()

    await checkout_card_declined.run(page, config, env, "run-003", "mobile_co")

    fill_calls = [(call.args[0], call.args[1]) for call in page.fill.call_args_list]
    filled_values = [value for _, value in fill_calls]

    assert SFCCSelectors.DECLINED_CARD_NUMBER in filled_values, (
        "Expected DECLINED_CARD_NUMBER to be filled in checkout_payment step"
    )
    assert SFCCSelectors.TEST_CARD_NUMBER not in filled_values, (
        "checkout_card_declined must NOT use TEST_CARD_NUMBER"
    )


@pytest.mark.asyncio
async def test_checkout_card_declined_has_10_steps() -> None:
    """The flow must produce exactly 10 StepResults."""
    page = _make_page_success()
    config = _make_config()
    env = _make_env()

    result = await checkout_card_declined.run(page, config, env, "run-003", "mobile_co")

    assert len(result.steps) == 10


# ---------------------------------------------------------------------------
# No time.sleep check (RNF-07)
# ---------------------------------------------------------------------------


def test_no_sleep_calls() -> None:
    """Verify that flow modules do not import or call time.sleep (RNF-07)."""
    flow_dir = Path(__file__).parent.parent / "src" / "executor" / "flows"
    flow_files = [
        flow_dir / "checkout_full.py",
        flow_dir / "checkout_card_declined.py",
    ]

    for flow_file in flow_files:
        source = flow_file.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            # Check for "import time" followed by time.sleep usage
            if isinstance(node, ast.Attribute):
                if (
                    isinstance(node.value, ast.Name)
                    and node.value.id == "time"
                    and node.attr == "sleep"
                ):
                    pytest.fail(
                        f"{flow_file.name}: found time.sleep call — "
                        "use wait_for_selector() / expect() instead (RNF-07)"
                    )

            # Check for "from time import sleep"
            if isinstance(node, ast.ImportFrom):
                if node.module == "time" and any(
                    alias.name == "sleep" for alias in (node.names or [])
                ):
                    pytest.fail(
                        f"{flow_file.name}: found 'from time import sleep' — "
                        "use wait_for_selector() / expect() instead (RNF-07)"
                    )
