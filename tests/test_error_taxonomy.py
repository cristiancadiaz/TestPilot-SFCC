"""Error-taxonomy coverage (U4 Phase C) — one path per error-taxonomy.md row.

Asserts the right HTTP code + ``error_code`` and that 5xx bodies never leak stack
traces, secret values or exception messages.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.schemas import EnvironmentConfig
from src.api.services.environment_registry import EnvironmentRegistry
from src.api.services.environment_resolver import EnvironmentResolver
from src.api.services.live_status_tracker import LiveStatusTracker
from src.api.services.run_orchestrator import RunOrchestrator
from src.api.stores import (
    InMemoryEnvironmentStore,
    InMemoryRunReportStore,
    InMemorySecretsClient,
)
from src.baseline import BaselineManager, InMemoryBaselineStore
from src.models import (
    BrowserProfile,
    FlowName,
    FlowResult,
    ProfileResult,
    ResolvedEnvironment,
    StepResult,
    SyntheticUserConfig,
    TrafficLight,
)

API_KEY = "test-key-123"
H = {"X-API-Key": API_KEY}

RunProfileFn = Callable[
    [BrowserProfile, FlowName, SyntheticUserConfig, ResolvedEnvironment, str],
    Awaitable[ProfileResult],
]


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", API_KEY)


def _ok_fake(*, orders_created: int = 0) -> RunProfileFn:
    async def _fake(
        profile: BrowserProfile,
        flow_name: FlowName,
        config: SyntheticUserConfig,
        env: ResolvedEnvironment,
        run_id: str,
    ) -> ProfileResult:
        flow_result = FlowResult(
            flow_name=flow_name,
            status="success",
            steps=[StepResult(name="s", status="success", duration_ms=100)],
            duration_ms=100,
            orders_created=0,
        )
        if orders_created:
            object.__setattr__(flow_result, "orders_created", orders_created)
        return ProfileResult(
            profile=profile, flow_result=flow_result, traffic_light=TrafficLight.GREEN
        )

    return _fake


def _raising_fake() -> RunProfileFn:
    async def _fake(*args: Any, **kwargs: Any) -> ProfileResult:
        raise RuntimeError("boom-secret-internal-detail")

    return _fake


def _slow_fake() -> RunProfileFn:
    async def _fake(
        profile: BrowserProfile,
        flow_name: FlowName,
        config: SyntheticUserConfig,
        env: ResolvedEnvironment,
        run_id: str,
    ) -> ProfileResult:
        await asyncio.sleep(0.05)
        return ProfileResult(
            profile=profile,
            flow_result=FlowResult(
                flow_name=flow_name,
                status="success",
                steps=[StepResult(name="s", status="success", duration_ms=100)],
                duration_ms=100,
                orders_created=0,
            ),
            traffic_light=TrafficLight.GREEN,
        )

    return _fake


def _make_app(
    run_profile: RunProfileFn,
    *,
    register_env: bool = True,
    active: bool = True,
    seed_secrets: bool = True,
    bad_secret: bool = False,
    timeout: int = 1800,
) -> FastAPI:
    env_store = InMemoryEnvironmentStore()
    secrets = InMemorySecretsClient()
    if seed_secrets:
        secrets.set(
            "sm/env",
            {"username": "infra"} if bad_secret else {"username": "i", "password": "p"},
        )
        secrets.set("sm/shopper", {"username": "s@testpilot.internal", "password": "p"})
    if register_env:
        env_store.put(
            EnvironmentConfig(
                environment_id="staging",
                store_url="https://staging.example.com",
                env_access_secret_path="sm/env",
                shopper_secret_path="sm/shopper",
                active=active,
            )
        )
    resolver = EnvironmentResolver(env_store, secrets)
    baseline = BaselineManager(InMemoryBaselineStore())
    reports = InMemoryRunReportStore()
    tracker = LiveStatusTracker()
    orchestrator = RunOrchestrator(
        resolver,
        baseline,
        reports,
        tracker,
        run_profile=run_profile,
        timeout_seconds=timeout,
    )
    registry = EnvironmentRegistry(env_store, secrets, resolver)
    return create_app(
        orchestrator=orchestrator,
        tracker=tracker,
        registry=registry,
        report_store=reports,
        serve_dashboard=False,
    )


def _payload(flows: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "v2",
        "environment_id": "staging",
        "flows": flows or ["checkout_full"],
        "mode": "gate",
        "profiles": ["mobile_co"],
        "products": [{"search_term": "camisa", "validate_variant": True}],
    }


def test_401_unauthorized() -> None:
    client = TestClient(_make_app(_ok_fake()))
    resp = client.post("/v1/run", json=_payload())
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "unauthorized"


def test_422_validation_failed_bad_enum() -> None:
    client = TestClient(_make_app(_ok_fake()))
    resp = client.post("/v1/run", json=_payload(flows=["nope"]), headers=H)
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "validation_failed"


def test_404_environment_not_found() -> None:
    client = TestClient(_make_app(_ok_fake(), register_env=False))
    resp = client.post("/v1/run", json=_payload(), headers=H)
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "environment_not_found"


def test_409_environment_inactive() -> None:
    client = TestClient(_make_app(_ok_fake(), active=False))
    resp = client.post("/v1/run", json=_payload(), headers=H)
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "environment_inactive"


def test_502_secret_not_found() -> None:
    client = TestClient(_make_app(_ok_fake(), seed_secrets=False))
    resp = client.post("/v1/run", json=_payload(), headers=H)
    assert resp.status_code == 502
    assert resp.json()["error_code"] == "secret_not_found"
    assert "Traceback" not in resp.text


def test_422_invalid_secret_path() -> None:
    client = TestClient(_make_app(_ok_fake(), bad_secret=True))
    resp = client.post("/v1/run", json=_payload(), headers=H)
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "invalid_secret_path"


def test_504_run_timeout() -> None:
    client = TestClient(_make_app(_slow_fake(), timeout=0))
    resp = client.post("/v1/run", json=_payload(), headers=H)
    assert resp.status_code == 504
    assert resp.json()["error_code"] == "run_timeout"


def test_500_invariant_violated() -> None:
    client = TestClient(_make_app(_ok_fake(orders_created=1)))
    resp = client.post("/v1/run", json=_payload(), headers=H)
    assert resp.status_code == 500
    assert resp.json()["error_code"] == "invariant_violated"


def test_500_internal_error_no_stack_trace_leak() -> None:
    client = TestClient(_make_app(_raising_fake()), raise_server_exceptions=False)
    resp = client.post("/v1/run", json=_payload(), headers=H)
    assert resp.status_code == 500
    body = resp.json()
    assert body["error_code"] == "internal_error"
    assert body["request_id"]
    # No stack trace / internal exception message leaks to the client.
    assert "Traceback" not in resp.text
    assert "boom-secret-internal-detail" not in resp.text
