"""Network capture wired into BOTH runner entry points (U7 / D-U7-1).

`run_profile` and `run_composition` attach a `network_summary` to every
ProfileResult; a composition produces one summary per executed flow. Playwright
is fully mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.executor.profiles import DESKTOP_CO
from src.executor.runner import FLOW_REGISTRY, run_composition, run_profile
from src.models import (
    Credentials,
    FlowResult,
    Product,
    ResolvedEnvironment,
    StepResult,
    SyntheticUserConfig,
)

SEQ = ["search_and_filter", "pdp_validation", "cart_review", "checkout_full"]


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


def _flow_result(name: str) -> FlowResult:
    return FlowResult(
        flow_name=name,  # type: ignore[arg-type]
        status="success",
        steps=[StepResult(name="step", status="success", duration_ms=10)],
        duration_ms=10,
        orders_created=0,
    )


def _fake_flow(name: str):  # type: ignore[no-untyped-def]
    async def _f(page, config, env, run_id, profile_id):  # type: ignore[no-untyped-def]
        return _flow_result(name)

    return _f


def _playwright_mock() -> MagicMock:
    """Mock with a page exposing ``.on`` (sync) and ``.evaluate`` (async, CWV)."""
    page = MagicMock()
    page.on = MagicMock()
    page.evaluate = AsyncMock(
        return_value={"lcp_ms": 1100, "cls": 0.02, "ttfb_ms": 250}
    )
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


@pytest.mark.asyncio
async def test_run_profile_attaches_network_summary() -> None:
    with (
        patch("src.executor.runner.async_playwright", return_value=_playwright_mock()),
        patch.dict(FLOW_REGISTRY, {"pdp_validation": _fake_flow("pdp_validation")}),
    ):
        result = await run_profile(
            DESKTOP_CO, "pdp_validation", _config(), _env(), "run-net"
        )

    ns = result.network_summary
    assert ns is not None
    assert ns.total_requests == 0  # no real events fired in the mock
    assert ns.web_vitals is not None and ns.web_vitals.lcp_ms == 1100
    assert ns.har_url == "run-net/desktop_co/pdp_validation/network.har.json"


@pytest.mark.asyncio
async def test_run_composition_attaches_summary_per_flow() -> None:
    registry = {n: _fake_flow(n) for n in SEQ}
    with (
        patch("src.executor.runner.async_playwright", return_value=_playwright_mock()),
        patch.dict(FLOW_REGISTRY, registry),
    ):
        results = await run_composition(DESKTOP_CO, SEQ, _config(), _env(), "run-comp")

    assert len(results) == 4
    assert all(r.network_summary is not None for r in results)
    # Each summary's HAR key carries that flow's name.
    assert results[1].network_summary.har_url.endswith(  # type: ignore[union-attr]
        "/pdp_validation/network.har.json"
    )
