"""POST /v1/run with ``full_journey`` (U5 integration — lifts the wave-1 422).

The orchestrator expands ``full_journey`` to its modular sequence and routes it to
``run_composition`` (one ProfileResult per flow). The composition is stubbed — no
browser. Verifies the expansion shape, multi-profile fan-out, and that a broken
link inside the journey still produces a 200 report with a RED verdict.
"""

from __future__ import annotations

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


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", API_KEY)


def _composition_stub(
    *, fail_at: str | None = None
) -> Any:
    """One ProfileResult per flow; if ``fail_at`` matches, that link fails and the
    rest are skipped (mirrors run_composition's contract)."""

    async def _fake(
        profile: BrowserProfile,
        flow_names: list[FlowName],
        config: SyntheticUserConfig,
        env: ResolvedEnvironment,
        run_id: str,
    ) -> list[ProfileResult]:
        results: list[ProfileResult] = []
        broken = False
        for flow_name in flow_names:
            status: Literal["success", "failed"]
            step_status: Literal["success", "failed", "skipped"]
            if broken:
                status, step_status = "failed", "skipped"
            elif flow_name == fail_at:
                status, step_status, broken = "failed", "failed", True
            else:
                status, step_status = "success", "success"
            results.append(
                ProfileResult(
                    profile=profile,
                    flow_result=FlowResult(
                        flow_name=flow_name,
                        status=status,
                        steps=[
                            StepResult(name="s", status=step_status, duration_ms=100)
                        ],
                        duration_ms=100,
                        orders_created=0,
                    ),
                    traffic_light=TrafficLight.GREEN,
                )
            )
        return results

    return _fake


async def _run_profile_unused(*_a: object, **_k: object) -> ProfileResult:
    raise AssertionError("run_profile must not be called for a full_journey run")


def _build(run_composition: Any) -> TestClient:
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
    secrets.set("sm/env", {"username": "infra", "password": "infra_pass"})
    secrets.set("sm/shopper", {"username": "s@testpilot.internal", "password": "x"})
    resolver = EnvironmentResolver(env_store, secrets)
    baseline = BaselineManager(InMemoryBaselineStore())
    reports = InMemoryRunReportStore()
    tracker = LiveStatusTracker()
    orchestrator = RunOrchestrator(
        resolver,
        baseline,
        reports,
        tracker,
        run_profile=_run_profile_unused,
        run_composition=run_composition,
    )
    return TestClient(create_app(orchestrator=orchestrator, tracker=tracker))


def _payload(profiles: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "v2",
        "environment_id": "staging",
        "flows": ["full_journey"],
        "mode": "gate",
        "profiles": profiles or ["mobile_co"],
        "products": [{"search_term": "camisa", "validate_variant": True}],
    }


def test_full_journey_returns_one_result_per_expanded_flow() -> None:
    client = _build(_composition_stub())
    resp = client.post("/v1/run", json=_payload(), headers=H)
    assert resp.status_code == 200  # was 422 in wave 1
    body = resp.json()
    flows = [pr["flow_result"]["flow_name"] for pr in body["profile_results"]]
    assert flows == ["search_and_filter", "pdp_validation", "cart_review", "checkout_full"]
    assert body["traffic_light"] == "green"


def test_full_journey_fans_out_per_profile() -> None:
    client = _build(_composition_stub())
    resp = client.post(
        "/v1/run", json=_payload(profiles=["mobile_co", "desktop_co"]), headers=H
    )
    assert resp.status_code == 200
    # 2 profiles × 4 expanded flows.
    assert len(resp.json()["profile_results"]) == 8


def test_full_journey_broken_link_yields_red_report() -> None:
    client = _build(_composition_stub(fail_at="pdp_validation"))
    resp = client.post("/v1/run", json=_payload(), headers=H)
    assert resp.status_code == 200
    body = resp.json()
    # A failed flow drives the deterministic verdict to RED (U3).
    assert body["traffic_light"] == "red"
    assert len(body["profile_results"]) == 4
