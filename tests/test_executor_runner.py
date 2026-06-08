"""Tests for src/executor/runner.py.

All Playwright browser interactions are fully mocked — no real browser is
launched. Covers:
  - Successful run_profile returns a ProfileResult.
  - PlaywrightError in browser launch -> ProfileResult(status='error'),
    not a raised exception (InfrastructureError handling).
  - orders_created != 0 from a flow -> AssertionError (invariant #1).
  - Flow dispatch uses FLOW_REGISTRY, not if/else.
  - InfrastructureError vs functional failure produce distinct statuses.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import Error as PlaywrightError

from src.executor.runner import FLOW_REGISTRY, run_profile
from src.models import (
    Credentials,
    FlowResult,
    ProfileResult,
    ResolvedEnvironment,
    StepResult,
    TrafficLight,
)
from src.executor.profiles import DESKTOP_CO


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_env() -> ResolvedEnvironment:
    return ResolvedEnvironment(
        environment_id="staging",
        store_url="https://staging.example.com",
        env_access=Credentials(username="infra", password="infra_pass"),
        shopper=Credentials(
            username="shopper@testpilot.internal", password="shopperpass"
        ),
    )


def _make_success_flow_result(flow_name: str = "checkout_full") -> FlowResult:
    return FlowResult(
        flow_name=flow_name,  # type: ignore[arg-type]
        status="success",
        steps=[
            StepResult(
                name="some_step",
                status="success",
                duration_ms=100,
                screenshot_state="final",
            )
        ],
        duration_ms=500,
        orders_created=0,
    )


def _make_failed_flow_result(flow_name: str = "checkout_full") -> FlowResult:
    return FlowResult(
        flow_name=flow_name,  # type: ignore[arg-type]
        status="failed",
        steps=[
            StepResult(
                name="some_step",
                status="failed",
                duration_ms=50,
                screenshot_state="fail",
            )
        ],
        duration_ms=50,
        orders_created=0,
    )


def _make_contaminated_flow_result(flow_name: str = "checkout_full") -> FlowResult:
    """A FlowResult with orders_created=1 — must trigger AssertionError."""
    result = FlowResult(
        flow_name=flow_name,  # type: ignore[arg-type]
        status="success",
        steps=[
            StepResult(name="step", status="success", duration_ms=10)
        ],
        duration_ms=10,
    )
    # Bypass Pydantic to inject a bad value (testing the assert guard).
    object.__setattr__(result, "orders_created", 1)
    return result


# ---------------------------------------------------------------------------
# Helpers to build the Playwright async-context-manager mock
# ---------------------------------------------------------------------------


def _build_playwright_mock(
    flow_result: FlowResult | None = None,
    raise_playwright_error: bool = False,
) -> MagicMock:
    """Build a mock for ``async_playwright()`` context manager.

    Args:
        flow_result:            The FlowResult the mock flow coroutine returns.
        raise_playwright_error: If True, ``browser.new_context`` raises
                                ``PlaywrightError`` to simulate an infra error.
    """
    page_mock = MagicMock()
    page_mock.screenshot = AsyncMock(return_value=None)

    context_mock = MagicMock()
    context_mock.new_page = AsyncMock(return_value=page_mock)
    context_mock.__aenter__ = AsyncMock(return_value=context_mock)
    context_mock.__aexit__ = AsyncMock(return_value=False)

    browser_mock = MagicMock()
    browser_mock.close = AsyncMock(return_value=None)

    if raise_playwright_error:
        browser_mock.new_context = AsyncMock(
            side_effect=PlaywrightError("net::ERR_NAME_NOT_RESOLVED")
        )
    else:
        browser_mock.new_context = AsyncMock(return_value=context_mock)

    chromium_mock = MagicMock()
    chromium_mock.launch = AsyncMock(return_value=browser_mock)

    playwright_instance = MagicMock()
    playwright_instance.chromium = chromium_mock

    playwright_ctx = MagicMock()
    playwright_ctx.__aenter__ = AsyncMock(return_value=playwright_instance)
    playwright_ctx.__aexit__ = AsyncMock(return_value=False)

    return playwright_ctx


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_profile_returns_profile_result() -> None:
    """Successful flow run -> ProfileResult with correct profile and flow_result."""
    from src.models import SyntheticUserConfig, Product

    config = SyntheticUserConfig(
        environment_id="staging",
        flows=["checkout_full"],
        profiles=["desktop_co"],
        products=[Product(search_term="shoes", validate_variant=False)],
        mode="gate",
    )
    env = _make_env()
    flow_result = _make_success_flow_result("checkout_full")

    playwright_ctx = _build_playwright_mock(flow_result=flow_result)

    async def _mock_flow_run(page, cfg, ev, run_id, profile_id):  # type: ignore[no-untyped-def]
        return flow_result

    with (
        patch("src.executor.runner.async_playwright", return_value=playwright_ctx),
        patch.dict(FLOW_REGISTRY, {"checkout_full": _mock_flow_run}),
    ):
        result = await run_profile(DESKTOP_CO, "checkout_full", config, env, "run-001")

    assert isinstance(result, ProfileResult)
    assert result.profile == DESKTOP_CO
    assert result.flow_result.status == "success"
    assert result.traffic_light == TrafficLight.GREEN


@pytest.mark.asyncio
async def test_infrastructure_error_handled() -> None:
    """PlaywrightError during browser launch -> ProfileResult with status='error'."""
    from src.models import SyntheticUserConfig, Product

    config = SyntheticUserConfig(
        environment_id="staging",
        flows=["checkout_full"],
        profiles=["desktop_co"],
        products=[Product(search_term="shoes", validate_variant=False)],
        mode="gate",
    )
    env = _make_env()

    playwright_ctx = _build_playwright_mock(raise_playwright_error=True)

    with patch("src.executor.runner.async_playwright", return_value=playwright_ctx):
        result = await run_profile(DESKTOP_CO, "checkout_full", config, env, "run-002")

    assert isinstance(result, ProfileResult)
    assert result.flow_result.status == "error"
    # The exception must NOT propagate.


@pytest.mark.asyncio
async def test_orders_created_assert_zero() -> None:
    """Flow returning orders_created=1 must trigger AssertionError (invariant #1)."""
    from src.models import SyntheticUserConfig, Product

    config = SyntheticUserConfig(
        environment_id="staging",
        flows=["checkout_full"],
        profiles=["desktop_co"],
        products=[Product(search_term="shoes", validate_variant=False)],
        mode="gate",
    )
    env = _make_env()
    contaminated = _make_contaminated_flow_result("checkout_full")

    playwright_ctx = _build_playwright_mock(flow_result=contaminated)

    async def _contaminated_flow(page, cfg, ev, run_id, profile_id):  # type: ignore[no-untyped-def]
        return contaminated

    with (
        patch("src.executor.runner.async_playwright", return_value=playwright_ctx),
        patch.dict(FLOW_REGISTRY, {"checkout_full": _contaminated_flow}),
    ):
        with pytest.raises(AssertionError, match="Zero-contamination violated"):
            await run_profile(DESKTOP_CO, "checkout_full", config, env, "run-003")


@pytest.mark.asyncio
async def test_flow_dispatch_uses_registry() -> None:
    """run_profile dispatches via FLOW_REGISTRY — the registry entry is called."""
    from src.models import SyntheticUserConfig, Product

    config = SyntheticUserConfig(
        environment_id="staging",
        flows=["checkout_full"],
        profiles=["desktop_co"],
        products=[Product(search_term="shoes", validate_variant=False)],
        mode="gate",
    )
    env = _make_env()
    flow_result = _make_success_flow_result("checkout_full")

    called_with: dict[str, object] = {}

    async def _spy_flow(page, cfg, ev, run_id, profile_id):  # type: ignore[no-untyped-def]
        called_with["run_id"] = run_id
        called_with["profile_id"] = profile_id
        return flow_result

    playwright_ctx = _build_playwright_mock(flow_result=flow_result)

    with (
        patch("src.executor.runner.async_playwright", return_value=playwright_ctx),
        patch.dict(FLOW_REGISTRY, {"checkout_full": _spy_flow}),
    ):
        await run_profile(DESKTOP_CO, "checkout_full", config, env, "run-dispatch")

    # The spy was called — registry-based dispatch confirmed.
    assert called_with.get("run_id") == "run-dispatch"
    assert called_with.get("profile_id") == "desktop_co"


@pytest.mark.asyncio
async def test_env_access_passed_as_http_credentials() -> None:
    """env_access credentials are injected into the browser context as HTTP basic
    auth (ADR-001) — flow code never handles raw credentials, and staging behind
    basic auth is reachable."""
    from src.models import SyntheticUserConfig, Product

    config = SyntheticUserConfig(
        environment_id="staging",
        flows=["checkout_full"],
        profiles=["desktop_co"],
        products=[Product(search_term="shoes", validate_variant=False)],
        mode="gate",
    )
    env = _make_env()  # env_access = infra / infra_pass
    flow_result = _make_success_flow_result("checkout_full")

    playwright_ctx = _build_playwright_mock(flow_result=flow_result)

    async def _mock_flow_run(page, cfg, ev, run_id, profile_id):  # type: ignore[no-untyped-def]
        return flow_result

    with (
        patch("src.executor.runner.async_playwright", return_value=playwright_ctx),
        patch.dict(FLOW_REGISTRY, {"checkout_full": _mock_flow_run}),
    ):
        await run_profile(DESKTOP_CO, "checkout_full", config, env, "run-auth")

    new_context = (
        playwright_ctx.__aenter__.return_value.chromium.launch.return_value.new_context
    )
    new_context.assert_awaited_once()
    assert new_context.await_args.kwargs["http_credentials"] == {
        "username": "infra",
        "password": "infra_pass",
    }


@pytest.mark.asyncio
async def test_infrastructure_error_distinct_from_app_error() -> None:
    """InfrastructureError -> status='error'; functional failure -> status='failed'."""
    from src.models import SyntheticUserConfig, Product

    config = SyntheticUserConfig(
        environment_id="staging",
        flows=["checkout_full"],
        profiles=["desktop_co"],
        products=[Product(search_term="shoes", validate_variant=False)],
        mode="gate",
    )
    env = _make_env()

    # Case 1: infrastructure error (PlaywrightError in browser launch).
    infra_ctx = _build_playwright_mock(raise_playwright_error=True)
    with patch("src.executor.runner.async_playwright", return_value=infra_ctx):
        infra_result = await run_profile(
            DESKTOP_CO, "checkout_full", config, env, "run-infra"
        )
    assert infra_result.flow_result.status == "error"

    # Case 2: functional failure (flow returns status='failed').
    failed_flow_result = _make_failed_flow_result("checkout_full")

    async def _failing_flow(page, cfg, ev, run_id, profile_id):  # type: ignore[no-untyped-def]
        return failed_flow_result

    app_ctx = _build_playwright_mock(flow_result=failed_flow_result)
    with (
        patch("src.executor.runner.async_playwright", return_value=app_ctx),
        patch.dict(FLOW_REGISTRY, {"checkout_full": _failing_flow}),
    ):
        app_result = await run_profile(
            DESKTOP_CO, "checkout_full", config, env, "run-app"
        )
    assert app_result.flow_result.status == "failed"

    # The two statuses must be distinct.
    assert infra_result.flow_result.status != app_result.flow_result.status
