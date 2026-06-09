"""Tests for ``run_composition`` (U5 D-U5-2) — chained full_journey execution.

All Playwright interactions are mocked. Verifies: one shared browser context/page
across the whole chain; generic registry dispatch (no if/else per flow); and skip
propagation — a broken link marks every subsequent link ``skipped`` (H6.3 AC3).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.executor.profiles import DESKTOP_CO
from src.executor.runner import FLOW_REGISTRY, run_composition
from src.models import (
    Credentials,
    FlowResult,
    Product,
    ResolvedEnvironment,
    StepResult,
    SyntheticUserConfig,
)

FULL_JOURNEY = ["search_and_filter", "pdp_validation", "cart_review", "checkout_full"]
ALL_SIX = [
    "checkout_full",
    "checkout_card_declined",
    "search_and_filter",
    "browse_discounted_products",
    "pdp_validation",
    "cart_review",
]


def _config() -> SyntheticUserConfig:
    return SyntheticUserConfig(
        environment_id="staging",
        flows=["full_journey"],
        profiles=["desktop_co"],
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


def _flow_result(
    name: str, status: Literal["success", "failed"] = "success"
) -> FlowResult:
    step_status: Literal["success", "failed"] = (
        "success" if status == "success" else "failed"
    )
    return FlowResult(
        flow_name=name,  # type: ignore[arg-type]
        status=status,
        steps=[StepResult(name="step", status=step_status, duration_ms=10)],
        duration_ms=10,
        orders_created=0,
    )


def _fake_flow(
    name: str,
    *,
    status: Literal["success", "failed"] = "success",
    seen_pages: list[object] | None = None,
    calls: list[str] | None = None,
) -> Callable[..., object]:
    async def _f(page, config, env, run_id, profile_id):  # type: ignore[no-untyped-def]
        if seen_pages is not None:
            seen_pages.append(page)
        if calls is not None:
            calls.append(name)
        return _flow_result(name, status)

    return _f


def _playwright_mock() -> MagicMock:
    """``async_playwright()`` mock — one browser, one context, one shared page."""
    page = MagicMock()
    context = MagicMock()
    context.new_page = AsyncMock(return_value=page)
    browser = MagicMock()
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()
    chromium = MagicMock()
    chromium.launch = AsyncMock(return_value=browser)
    instance = MagicMock()
    instance.chromium = chromium
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=instance)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# Shared context + generic dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_composition_shares_one_context_across_the_chain() -> None:
    seen: list[object] = []
    registry = {n: _fake_flow(n, seen_pages=seen) for n in FULL_JOURNEY}

    with (
        patch("src.executor.runner.async_playwright", return_value=_playwright_mock()),
        patch.dict(FLOW_REGISTRY, registry),
    ):
        results = await run_composition(
            DESKTOP_CO, FULL_JOURNEY, _config(), _env(), "run-comp"
        )

    assert [r.flow_result.flow_name for r in results] == FULL_JOURNEY
    assert all(r.flow_result.status == "success" for r in results)
    # Every flow received the SAME page object → one shared browser context.
    assert len({id(p) for p in seen}) == 1


@pytest.mark.asyncio
async def test_composition_dispatches_all_six_generically() -> None:
    """Every catalog flow dispatches via the registry lookup (no if/else)."""
    calls: list[str] = []
    registry = {n: _fake_flow(n, calls=calls) for n in ALL_SIX}

    with (
        patch("src.executor.runner.async_playwright", return_value=_playwright_mock()),
        patch.dict(FLOW_REGISTRY, registry),
    ):
        results = await run_composition(
            DESKTOP_CO, ALL_SIX, _config(), _env(), "run-six"
        )

    assert len(results) == 6
    assert calls == ALL_SIX  # all six invoked, in order, via the registry


# ---------------------------------------------------------------------------
# Skip propagation (H6.3 AC3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broken_link_skips_remaining_flows() -> None:
    # Link 2 (pdp_validation) fails → links 3 & 4 must be skipped.
    registry = {
        "search_and_filter": _fake_flow("search_and_filter"),
        "pdp_validation": _fake_flow("pdp_validation", status="failed"),
        "cart_review": _fake_flow("cart_review"),
        "checkout_full": _fake_flow("checkout_full"),
    }

    with (
        patch("src.executor.runner.async_playwright", return_value=_playwright_mock()),
        patch.dict(FLOW_REGISTRY, registry),
    ):
        results = await run_composition(
            DESKTOP_CO, FULL_JOURNEY, _config(), _env(), "run-broken"
        )

    assert results[0].flow_result.status == "success"
    assert results[1].flow_result.status == "failed"
    # Remaining links present but skipped (one skipped step each).
    assert results[2].flow_result.steps[0].status == "skipped"
    assert results[3].flow_result.steps[0].status == "skipped"
    assert all(r.flow_result.orders_created == 0 for r in results)
