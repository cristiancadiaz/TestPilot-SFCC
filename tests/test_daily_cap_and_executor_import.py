from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.stores import InMemoryRunReportStore, InMemoryEnvironmentStore, InMemorySecretsClient
from src.api.services.environment_resolver import EnvironmentResolver
from src.api.services.run_orchestrator import RunOrchestrator
from src.baseline import BaselineManager, InMemoryBaselineStore
from src.api.services.live_status_tracker import LiveStatusTracker
from src.api.schemas import EnvironmentConfig
from src.models import FlowResult, StepResult, ProfileResult, TrafficLight

API_KEY = "test-key-123"
H = {"X-API-Key": API_KEY}


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", API_KEY)


def _fake_run_profile():
    async def _fake(profile, flow_name, config, env, run_id):
        flow_result = FlowResult(
            flow_name=flow_name,
            status="success",
            steps=[StepResult(name="final", status="success", duration_ms=1000, screenshot_state="final")],
            duration_ms=1000,
            orders_created=0,
        )
        return ProfileResult(profile=profile, flow_result=flow_result, traffic_light=TrafficLight.GREEN)

    return _fake


def _build():
    env_store = InMemoryEnvironmentStore()
    secrets = InMemorySecretsClient()
    env_store.put(EnvironmentConfig(environment_id="staging", store_url="https://staging.example.com", env_access_secret_path="sm/env", shopper_secret_path="sm/shopper", active=True))
    secrets.set("sm/env", {"username": "infra", "password": "x"})
    secrets.set("sm/shopper", {"username": "shopper@testpilot.internal", "password": "x"})
    resolver = EnvironmentResolver(env_store, secrets)
    baseline = BaselineManager(InMemoryBaselineStore())
    reports = InMemoryRunReportStore()
    tracker = LiveStatusTracker()
    orchestrator = RunOrchestrator(resolver, baseline, reports, tracker, run_profile=_fake_run_profile())
    app = create_app(orchestrator=orchestrator, tracker=tracker, serve_dashboard=False)
    return TestClient(app), reports


def _payload():
    return {
        "schema_version": "v2",
        "environment_id": "staging",
        "flows": ["checkout_full"],
        "mode": "gate",
        "profiles": ["mobile_co"],
        "products": [{"search_term": "camisa", "validate_variant": True}],
    }


def test_daily_cap_enforced_after_10_runs() -> None:
    client, reports = _build()
    # Post 10 runs
    for _ in range(10):
        resp = client.post("/v1/run", json=_payload(), headers=H)
        assert resp.status_code == 200
    # 11th should be rate-limited
    resp = client.post("/v1/run", json=_payload(), headers=H)
    assert resp.status_code == 429
    assert resp.json()["error_code"] == "rate_limited"


def test_executor_folder_does_not_import_agents() -> None:
    import inspect
    import pkgutil
    import importlib
    import src.executor
    # Iterate modules in src.executor package and assert source does not reference 'src.agents'
    package = src.executor
    prefix = package.__name__ + "."
    for finder, name, ispkg in pkgutil.walk_packages(package.__path__, prefix):
        module = importlib.import_module(name)
        try:
            src = inspect.getsource(module)
        except (OSError, TypeError):
            continue
        assert "src.agents" not in src, f"module {name} imports src.agents"
