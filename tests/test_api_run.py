"""Tests for POST /v1/run and /health (U4 Phase A — the E2E spine).

The executor is fully mocked (an async ``run_profile`` stub) — no browser. Covers
auth, validation, environment resolution, the orchestrator wiring U1→U3→U2, the
gate-only baseline guard, and the zero-contamination invariant.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.schemas import EnvironmentConfig
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


def _fake_run_profile(
    *,
    status: Literal["success", "failed", "error"] = "success",
    duration_ms: int = 120_000,
    orders_created: int = 0,
) -> RunProfileFn:
    async def _fake(
        profile: BrowserProfile,
        flow_name: FlowName,
        config: SyntheticUserConfig,
        env: ResolvedEnvironment,
        run_id: str,
    ) -> ProfileResult:
        step_status: Literal["success", "failed"] = (
            "success" if status == "success" else "failed"
        )
        flow_result = FlowResult(
            flow_name=flow_name,
            status=status,
            steps=[
                StepResult(
                    name="final",
                    status=step_status,
                    duration_ms=duration_ms,
                    screenshot_state="final" if status == "success" else "fail",
                )
            ],
            duration_ms=duration_ms,
            orders_created=0,
        )
        if orders_created:
            object.__setattr__(flow_result, "orders_created", orders_created)
        return ProfileResult(
            profile=profile, flow_result=flow_result, traffic_light=TrafficLight.GREEN
        )

    return _fake


def _build(
    run_profile: RunProfileFn, *, seed_env: bool = True
) -> tuple[TestClient, BaselineManager, InMemoryRunReportStore, LiveStatusTracker]:
    env_store = InMemoryEnvironmentStore()
    secrets = InMemorySecretsClient()
    if seed_env:
        env_store.put(
            EnvironmentConfig(
                environment_id="staging",
                store_url="https://staging.example.com",
                env_access_secret_path="sm/env",
                shopper_secret_path="sm/shopper",
                active=True,
            )
        )
        secrets.set("sm/env", {"username": "infra", "password": "infra_pass"})
        secrets.set(
            "sm/shopper",
            {"username": "shopper@testpilot.internal", "password": "x"},
        )
    resolver = EnvironmentResolver(env_store, secrets)
    baseline = BaselineManager(InMemoryBaselineStore())
    reports = InMemoryRunReportStore()
    tracker = LiveStatusTracker()
    orchestrator = RunOrchestrator(
        resolver, baseline, reports, tracker, run_profile=run_profile
    )
    app = create_app(orchestrator=orchestrator, tracker=tracker)
    return TestClient(app), baseline, reports, tracker


def _payload(
    *,
    flows: list[str] | None = None,
    mode: str = "gate",
    profiles: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "v2",
        "environment_id": "staging",
        "flows": flows or ["checkout_full"],
        "mode": mode,
        "profiles": profiles or ["mobile_co"],
        "products": [{"search_term": "camisa", "validate_variant": True}],
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_post_run_ok_returns_report_and_run_id_header() -> None:
    client, _, reports, tracker = _build(_fake_run_profile())
    resp = client.post("/v1/run", json=_payload(), headers=H)
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"]
    assert body["traffic_light"] in ("green", "yellow", "red")
    assert "orders_created" not in body  # excluded from the contract
    assert resp.headers["X-Run-Id"] == body["run_id"]
    # Persisted + tracked.
    assert reports.get(body["run_id"]) is not None
    assert tracker.get(body["run_id"]) is not None


def test_post_run_multi_profile_multi_flow() -> None:
    client, _, _, _ = _build(_fake_run_profile())
    resp = client.post(
        "/v1/run",
        json=_payload(
            flows=["checkout_full", "checkout_card_declined"],
            profiles=["mobile_co", "desktop_co"],
        ),
        headers=H,
    )
    assert resp.status_code == 200
    assert len(resp.json()["profile_results"]) == 4  # 2 profiles × 2 flows


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_post_run_without_api_key_is_401() -> None:
    client, _, _, _ = _build(_fake_run_profile())
    resp = client.post("/v1/run", json=_payload())
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "unauthorized"


def test_post_run_with_bad_api_key_is_401() -> None:
    client, _, _, _ = _build(_fake_run_profile())
    resp = client.post("/v1/run", json=_payload(), headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_post_run_invalid_flow_enum_is_422() -> None:
    client, _, _, _ = _build(_fake_run_profile())
    resp = client.post("/v1/run", json=_payload(flows=["nonsense"]), headers=H)
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "validation_failed"


def test_post_run_full_journey_rejected_in_wave1() -> None:
    client, _, _, _ = _build(_fake_run_profile())
    resp = client.post("/v1/run", json=_payload(flows=["full_journey"]), headers=H)
    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "validation_failed"
    assert body["details"]["flow"] == "full_journey"


# ---------------------------------------------------------------------------
# Environment resolution
# ---------------------------------------------------------------------------


def test_post_run_unknown_environment_is_404() -> None:
    client, _, _, _ = _build(_fake_run_profile(), seed_env=False)
    resp = client.post("/v1/run", json=_payload(), headers=H)
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "environment_not_found"


# ---------------------------------------------------------------------------
# Baseline: gate-only guard (C11)
# ---------------------------------------------------------------------------


def test_gate_run_feeds_baseline_exploratory_does_not() -> None:
    client, baseline, _, _ = _build(_fake_run_profile())
    client.post("/v1/run", json=_payload(mode="gate"), headers=H)
    assert len(baseline.list_runs("staging", 50, 0)) == 1
    client.post("/v1/run", json=_payload(mode="exploratory"), headers=H)
    # Exploratory run must NOT be persisted to the baseline.
    assert len(baseline.list_runs("staging", 50, 0)) == 1


# ---------------------------------------------------------------------------
# Zero-contamination invariant (#1)
# ---------------------------------------------------------------------------


def test_orders_created_nonzero_is_500_invariant_violated() -> None:
    client, _, _, _ = _build(_fake_run_profile(orders_created=1))
    resp = client.post("/v1/run", json=_payload(), headers=H)
    assert resp.status_code == 500
    assert resp.json()["error_code"] == "invariant_violated"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health_ok() -> None:
    client, _, _, _ = _build(_fake_run_profile())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_503_when_probe_fails() -> None:
    client, _, _, _ = _build(_fake_run_profile())
    client.app.state.health_probe = lambda: False  # type: ignore[attr-defined]
    resp = client.get("/health")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------


def test_security_headers_present() -> None:
    client, _, _, _ = _build(_fake_run_profile())
    resp = client.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in resp.headers
    assert resp.headers["X-Request-Id"]
