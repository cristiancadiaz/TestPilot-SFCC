"""Tests for the U5 journey flows against a fully mocked Playwright ``Page``.

No real browser. Each flow returns a ``FlowResult``; a failing step marks the
subsequent steps ``skipped`` (H6.3); cart_review's setup steps carry
``phase="setup"`` (H6.2 AC3); browse_discounted reads PLP+PDP prices for the U6
collectors; and ``orders_created`` is ALWAYS 0 (journey flows never pay).
"""

from __future__ import annotations

from collections.abc import Iterable
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.executor.flows import (
    browse_discounted_products,
    cart_review,
    pdp_validation,
    search_and_filter,
)
from src.executor.selectors import SFCCSelectors
from src.models import (
    Credentials,
    Product,
    ResolvedEnvironment,
    SyntheticUserConfig,
)


def _config() -> SyntheticUserConfig:
    return SyntheticUserConfig(
        environment_id="staging",
        flows=["search_and_filter"],
        profiles=["mobile_co"],
        products=[Product(search_term="camisa", validate_variant=True)],
        mode="gate",
    )


def _env() -> ResolvedEnvironment:
    return ResolvedEnvironment(
        environment_id="staging",
        store_url="https://staging.example.com",
        env_access=Credentials(username="infra", password="infra_pass"),
        shopper=Credentials(username="s@testpilot.internal", password="p"),
    )


def _make_page(
    *,
    fail_on: Iterable[str] = (),
    text: str = "$10.00",
    disabled: bool = False,
) -> MagicMock:
    """A mocked async ``Page``. Selectors in ``fail_on`` raise on wait/click."""
    blocked = frozenset(fail_on)

    def _locator(selector: str, *_a: object, **_k: object) -> MagicMock:
        loc = MagicMock()

        async def _wait_for(*_a: object, **_k: object) -> None:
            if selector in blocked:
                raise RuntimeError(f"selector not found: {selector}")

        loc.wait_for = AsyncMock(side_effect=_wait_for)
        loc.click = AsyncMock()
        loc.text_content = AsyncMock(return_value=text)
        loc.is_disabled = AsyncMock(return_value=disabled)
        loc.first = loc  # `.first` resolves to the same async-capable mock
        return loc

    async def _wait_for_selector(selector: str, *_a: object, **_k: object) -> object:
        if selector in blocked:
            raise RuntimeError(f"selector not found: {selector}")
        return MagicMock()

    async def _click(selector: str, *_a: object, **_k: object) -> None:
        if selector in blocked:
            raise RuntimeError(f"click target not found: {selector}")

    page = MagicMock()
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.wait_for_selector = AsyncMock(side_effect=_wait_for_selector)
    page.fill = AsyncMock()
    page.click = AsyncMock(side_effect=_click)
    page.locator = MagicMock(side_effect=_locator)
    return page


_FLOWS = {
    "search_and_filter": (search_and_filter, 5),
    "browse_discounted_products": (browse_discounted_products, 5),
    "pdp_validation": (pdp_validation, 7),
    "cart_review": (cart_review, 9),
}


# ---------------------------------------------------------------------------
# Happy path — each flow returns a successful FlowResult of the right shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("flow_name", sorted(_FLOWS))
async def test_flow_runs_clean(flow_name: str) -> None:
    module, expected_steps = _FLOWS[flow_name]
    page = _make_page()
    result = await module.run(page, _config(), _env(), "run-1", "mobile_co")

    assert result.flow_name == flow_name
    assert result.status == "success"
    assert len(result.steps) == expected_steps
    assert all(s.status == "success" for s in result.steps)
    # ADR-003: terminal step carries the "final" evidence marker.
    assert result.steps[-1].screenshot_state == "final"
    # Invariant #1: a journey flow never creates an order.
    assert result.orders_created == 0


# ---------------------------------------------------------------------------
# cart_review setup phase (H6.2 AC3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cart_review_setup_steps_tagged_setup_phase() -> None:
    result = await cart_review.run(_make_page(), _config(), _env(), "run-2", "mobile_co")
    by_name = {s.name: s for s in result.steps}
    for setup_step in ("search_product", "open_product", "add_to_cart", "open_cart"):
        assert by_name[setup_step].phase == "setup", setup_step
    # The validation steps are NOT setup.
    assert by_name["cart_price_consistency"].phase == "flow"


# ---------------------------------------------------------------------------
# browse_discounted reads PLP + PDP prices (feeds U6 collectors)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_browse_discounted_reads_plp_and_pdp_prices() -> None:
    page = _make_page()
    result = await browse_discounted_products.run(
        page, _config(), _env(), "run-3", "mobile_co"
    )
    assert result.status == "success"
    located = [c.args[0] for c in page.locator.call_args_list]
    assert SFCCSelectors.PROMOTIONS_DISCOUNTED_PRICE in located  # PLP price captured
    assert SFCCSelectors.PDP_PRICE in located  # PDP price compared


# ---------------------------------------------------------------------------
# Failure propagation (H6.3): a failed step skips everything after it
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_step_skips_subsequent_steps() -> None:
    # Break the PLP result-count check → plp_results_validation fails.
    page = _make_page(fail_on={SFCCSelectors.PLP_RESULT_COUNT})
    result = await search_and_filter.run(page, _config(), _env(), "run-4", "mobile_co")

    assert result.status == "failed"
    statuses = [s.status for s in result.steps]
    # env_access + search succeed, plp_results_validation fails, rest skipped.
    assert statuses == ["success", "success", "failed", "skipped", "skipped"]
    assert result.orders_created == 0
