"""Tests for the run history + status endpoints (U4 Phase B, S2/S7)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
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


def _fake_run_profile() -> RunProfileFn:
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
            steps=[
                StepResult(
                    name="final",
                    status="success",
                    duration_ms=120_000,
                    screenshot_state="final",
                )
            ],
            duration_ms=120_000,
            orders_created=0,
        )
        return ProfileResult(
            profile=profile, flow_result=flow_result, traffic_light=TrafficLight.GREEN
        )

    return _fake


def _build() -> tuple[TestClient, InMemoryEnvironmentStore]:
    env_store = InMemoryEnvironmentStore()
    secrets = InMemorySecretsClient()
    env_store.put(
        EnvironmentConfig(
            environment_id="staging",
            store_url="https://staging.example.com",
            env_access_secret_path="sm/env",
            shopper_secret_path="sm/shopper",
            active=True,
        )
    )
    secrets.set("sm/env", {"username": "infra", "password": "p"})
    secrets.set("sm/shopper", {"username": "s@testpilot.internal", "password": "p"})
    resolver = EnvironmentResolver(env_store, secrets)
    baseline = BaselineManager(InMemoryBaselineStore())
    reports = InMemoryRunReportStore()
    tracker = LiveStatusTracker()
    orchestrator = RunOrchestrator(
        resolver, baseline, reports, tracker, run_profile=_fake_run_profile()
    )
    registry = EnvironmentRegistry(env_store, secrets, resolver)
    app = create_app(
        orchestrator=orchestrator,
        tracker=tracker,
        registry=registry,
        report_store=reports,
    )
    return TestClient(app), env_store


def _payload(mode: str = "gate") -> dict[str, Any]:
    return {
        "schema_version": "v2",
        "environment_id": "staging",
        "flows": ["checkout_full"],
        "mode": mode,
        "profiles": ["mobile_co"],
        "products": [{"search_term": "camisa", "validate_variant": True}],
    }


def _run(client: TestClient) -> str:
    resp = client.post("/v1/run", json=_payload(), headers=H)
    assert resp.status_code == 200
    run_id: str = resp.json()["run_id"]
    return run_id


# ---------------------------------------------------------------------------
# GET /v1/runs/{id}
# ---------------------------------------------------------------------------


def test_get_run_by_id() -> None:
    client, _ = _build()
    run_id = _run(client)
    resp = client.get(f"/v1/runs/{run_id}", headers=H)
    assert resp.status_code == 200
    assert resp.json()["run_id"] == run_id


def test_get_unknown_run_is_404() -> None:
    client, _ = _build()
    resp = client.get(
        "/v1/runs/550e8400-e29b-41d4-a716-446655440000", headers=H
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "run_not_found"


def test_get_run_bad_uuid_is_422() -> None:
    client, _ = _build()
    resp = client.get("/v1/runs/not-a-uuid", headers=H)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /v1/runs/latest
# ---------------------------------------------------------------------------


def test_latest_no_runs_is_404() -> None:
    client, _ = _build()
    resp = client.get("/v1/runs/latest", headers=H)
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "no_runs_yet"


def test_latest_returns_gate_run_with_meta() -> None:
    client, _ = _build()
    _run(client)
    resp = client.get("/v1/runs/latest", headers=H)
    assert resp.status_code == 200
    body = resp.json()
    assert "report" in body
    assert body["ttl_ok"] is True
    assert body["age_seconds"] >= 0


def test_latest_ignores_exploratory() -> None:
    client, _ = _build()
    # Only an exploratory run exists -> no gate run -> 404.
    client.post("/v1/run", json=_payload(mode="exploratory"), headers=H)
    resp = client.get("/v1/runs/latest", headers=H)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /v1/runs (list)
# ---------------------------------------------------------------------------


def test_list_runs_returns_items() -> None:
    client, _ = _build()
    _run(client)
    _run(client)
    resp = client.get("/v1/runs", headers=H)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert body["has_more"] is False
    assert body["items"][0]["orders_created"] == 0


def test_list_runs_filter_by_environment() -> None:
    client, _ = _build()
    _run(client)
    empty = client.get("/v1/runs?environment_id=sandbox", headers=H).json()
    assert empty["total"] == 0


def test_list_runs_pagination_has_more() -> None:
    client, _ = _build()
    _run(client)
    _run(client)
    page1 = client.get("/v1/runs?page=1&page_size=1", headers=H).json()
    assert page1["total"] == 2
    assert len(page1["items"]) == 1
    assert page1["has_more"] is True


# ---------------------------------------------------------------------------
# GET /v1/runs/{id}/status
# ---------------------------------------------------------------------------


def test_run_status_after_run() -> None:
    client, _ = _build()
    run_id = _run(client)
    resp = client.get(f"/v1/runs/{run_id}/status", headers=H)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "completed"
    assert body["orders_created"] == 0


def test_run_status_unknown_is_404() -> None:
    client, _ = _build()
    resp = client.get(
        "/v1/runs/550e8400-e29b-41d4-a716-446655440000/status", headers=H
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 409 environment_inactive on run
# ---------------------------------------------------------------------------


def test_run_against_inactive_environment_is_409() -> None:
    client, _ = _build()
    client.delete("/v1/environments/staging", headers=H)  # deactivate
    resp = client.post("/v1/run", json=_payload(), headers=H)
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "environment_inactive"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_runs_require_auth() -> None:
    client, _ = _build()
    assert client.get("/v1/runs").status_code == 401
