"""E8 acceptance tests — executable BDD traced to gherkin-scenarios.md.

Each test implements one Gherkin scenario from
``aidlc-docs/inception/user-stories/gherkin-scenarios.md`` against the real
wave-1 API stack (FastAPI TestClient + stubbed executor — no live storefront).

`pytest-bdd` is intentionally NOT used (avoids a new dependency); the scenario is
named in each docstring for traceability. Contract assertions validate live
responses against the JSON Schemas in ``specs/``.

Note on the contract: the v2 schema uses snake_case (`run_id`, `traffic_light`,
`ttl_ok`) — the Gherkin's camelCase (`testRunId`, `trafficLight`, `ttlOk`) predates
the schema rename. These tests assert the authoritative v2 contract.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

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
from src.baseline import (
    BaselineManager,
    InMemoryBaselineStore,
    calculate_p95,
    compute_traffic_light,
)
from src.models import (
    BrowserProfile,
    FlowName,
    FlowResult,
    ProfileResult,
    ResolvedEnvironment,
    RunRecord,
    StepResult,
    SyntheticUserConfig,
    TrafficLight,
)

API_KEY = "test-key-123"
H = {"X-API-Key": API_KEY}

_REPORT_SCHEMA = Draft202012Validator(
    json.loads(
        (Path(__file__).resolve().parents[1] / "specs" / "execution_report.schema.json")
        .read_text(encoding="utf-8")
    )
)

RunProfileFn = Callable[
    [BrowserProfile, FlowName, SyntheticUserConfig, ResolvedEnvironment, str],
    Awaitable[ProfileResult],
]


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", API_KEY)


def _executor(*, orders_created: int = 0) -> RunProfileFn:
    async def _fake(
        profile: BrowserProfile,
        flow_name: FlowName,
        config: SyntheticUserConfig,
        env: ResolvedEnvironment,
        run_id: str,
    ) -> ProfileResult:
        # The synthetic shopper email is always @testpilot.internal (zero-contam).
        assert env.shopper.username.endswith("@testpilot.internal")
        flow_result = FlowResult(
            flow_name=flow_name,
            status="success",
            steps=[
                StepResult(
                    name="payment_failure_validation",
                    status="success",
                    duration_ms=120_000,
                    screenshot_state="final",
                )
            ],
            duration_ms=120_000,
            orders_created=0,
        )
        if orders_created:
            object.__setattr__(flow_result, "orders_created", orders_created)
        return ProfileResult(
            profile=profile, flow_result=flow_result, traffic_light=TrafficLight.GREEN
        )

    return _fake


def _build(run_profile: RunProfileFn, *, seed_env: bool = True) -> TestClient:
    env_store = InMemoryEnvironmentStore()
    secrets = InMemorySecretsClient()
    if seed_env:
        env_store.put(
            EnvironmentConfig(
                environment_id="staging",
                store_url="https://staging.example.com",
                env_access_secret_path="testpilot/staging/env-access",
                shopper_secret_path="testpilot/staging/shopper",
                active=True,
            )
        )
        secrets.set("testpilot/staging/env-access", {"username": "infra", "password": "p"})
        secrets.set(
            "testpilot/staging/shopper",
            {"username": "shopper@testpilot.internal", "password": "p"},
        )
    resolver = EnvironmentResolver(env_store, secrets)
    baseline = BaselineManager(InMemoryBaselineStore())
    reports = InMemoryRunReportStore()
    tracker = LiveStatusTracker()
    orchestrator = RunOrchestrator(
        resolver, baseline, reports, tracker, run_profile=run_profile
    )
    registry = EnvironmentRegistry(env_store, secrets, resolver)
    app = create_app(
        orchestrator=orchestrator,
        tracker=tracker,
        registry=registry,
        report_store=reports,
        serve_dashboard=False,
    )
    return TestClient(app)


def _registry_client() -> TestClient:
    """Client whose registry has seeded secrets (so create succeeds)."""
    env_store = InMemoryEnvironmentStore()
    secrets = InMemorySecretsClient()
    secrets.set("testpilot/staging/env-access", {"username": "infra", "password": "p"})
    secrets.set(
        "testpilot/staging/shopper",
        {"username": "shopper@testpilot.internal", "password": "p"},
    )
    resolver = EnvironmentResolver(env_store, secrets)
    registry = EnvironmentRegistry(env_store, secrets, resolver)
    return TestClient(create_app(registry=registry, serve_dashboard=False))


def _run_payload(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": "v2",
        "environment_id": "staging",
        "flows": ["checkout_full"],
        "mode": "gate",
        "profiles": ["mobile_co"],
        "products": [{"search_term": "camisa roja", "validate_variant": True}],
    }
    base.update(over)
    return base


# ===========================================================================
# Feature: Environment Registry
# ===========================================================================


def test_register_staging_environment_secret_paths_only() -> None:
    """Scenario: Register staging environment with secret paths only."""
    client = _registry_client()
    resp = client.post(
        "/v1/environments",
        headers=H,
        json={
            "environment_id": "staging",
            "store_url": "https://staging.example.com",
            "env_access_secret_path": "testpilot/staging/env-access",
            "shopper_secret_path": "testpilot/staging/shopper",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    # The response carries only secret PATHS — never secret values.
    assert body["env_access_secret_path"] == "testpilot/staging/env-access"
    assert "password" not in body
    assert "username" not in body


def test_reject_environment_payload_with_credential_values() -> None:
    """Scenario: Reject environment payload containing credential values."""
    client = _registry_client()
    resp = client.post(
        "/v1/environments",
        headers=H,
        json={
            "environment_id": "staging",
            "store_url": "https://staging.example.com",
            "env_access_secret_path": "testpilot/staging/env-access",
            "shopper_secret_path": "testpilot/staging/shopper",
            "password": "leaked-secret",  # forbidden extra field
        },
    )
    assert resp.status_code == 422  # extra="forbid" rejects credential values
    # No environment record was created.
    assert client.get("/v1/environments", headers=H).json() == []


# ===========================================================================
# Feature: Structured Run Execution
# ===========================================================================


def test_launch_checkout_run_with_structured_config() -> None:
    """Scenario: Launch checkout run with structured SyntheticUserConfig."""
    client = _build(_executor())
    resp = client.post(
        "/v1/run",
        headers=H,
        json=_run_payload(
            flows=["checkout_full", "checkout_card_declined"],
            profiles=["mobile_co", "desktop_co", "desktop_ec"],
        ),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"]  # the v2 contract field (Gherkin's testRunId)
    assert resp.headers["X-Run-Id"] == body["run_id"]
    # One result per profile × flow (3 × 2).
    assert len(body["profile_results"]) == 6
    _REPORT_SCHEMA.validate(body)  # contract: response matches ExecutionReport v2


def test_reject_run_config_with_unsupported_flow() -> None:
    """Scenario: Reject run config with unsupported flow ('return-order')."""
    client = _build(_executor())
    resp = client.post("/v1/run", headers=H, json=_run_payload(flows=["return-order"]))
    assert resp.status_code == 422
    # No run record saved (history stays empty).
    assert client.get("/v1/runs", headers=H).json()["total"] == 0


# ===========================================================================
# Feature: Zero Order Contamination
# ===========================================================================


def test_checkout_fails_payment_creates_no_order() -> None:
    """Scenario: Checkout flow fails payment by design and creates no order."""
    client = _build(_executor())
    resp = client.post("/v1/run", headers=H, json=_run_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert "orders_created" not in body  # never published; invariant held internally
    _REPORT_SCHEMA.validate(body)  # the ExecutionReport is emitted


def test_block_report_generation_if_order_detected() -> None:
    """Scenario: Block report generation if an order is detected."""
    client = _build(_executor(orders_created=1))
    resp = client.post("/v1/run", headers=H, json=_run_payload())
    assert resp.status_code == 500
    assert resp.json()["error_code"] == "invariant_violated"


# ===========================================================================
# Feature: CI/CD Deploy Gate Consumption
# ===========================================================================


def test_cicd_reads_latest_fresh_green_report() -> None:
    """Scenario: CI/CD agent reads latest fresh green report."""
    client = _build(_executor())
    client.post("/v1/run", headers=H, json=_run_payload(mode="gate"))
    resp = client.get("/v1/runs/latest", headers=H)
    assert resp.status_code == 200
    body = resp.json()
    assert body["report"]["traffic_light"] == "green"
    assert body["ttl_ok"] is True
    assert body["age_seconds"] < 14_400
    _REPORT_SCHEMA.validate(body["report"])  # schema matches ExecutionReport


def test_cicd_cannot_read_latest_without_api_key() -> None:
    """Scenario: CI/CD agent cannot read latest report without API key."""
    client = _build(_executor())
    client.post("/v1/run", headers=H, json=_run_payload())
    resp = client.get("/v1/runs/latest")  # no X-API-Key
    assert resp.status_code == 401
    # Auth is checked before any store lookup — the response reveals no run data.
    text = resp.text.lower()
    assert "traffic_light" not in text
    assert "run_id" not in text


# ===========================================================================
# Feature: Baseline Bootstrap
# ===========================================================================


def test_bootstrap_mode_prevents_yellow_alerts() -> None:
    """Scenario: Bootstrap mode prevents yellow performance alerts (13 runs)."""
    manager = BaselineManager(InMemoryBaselineStore())
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(13):  # < BOOTSTRAP_MIN_RUNS (14)
        manager.save_run(
            RunRecord(
                run_id=f"r{i}",
                environment_id="staging",
                profile_name="mobile_co",
                flow_name="checkout_full",
                duration_ms=100_000,
                status="success",
                created_at=base + timedelta(days=i),
            ),
            mode="gate",
        )
    comparison = manager.get_baseline_comparison(
        "staging", "mobile_co", "checkout_full", current_ms=999_999  # much slower
    )
    assert comparison.bootstrap_mode is True
    verdict = compute_traffic_light(
        current_ms=999_999, p95_ms=comparison.p95_ms, bootstrap=comparison.bootstrap_mode
    )
    assert verdict == TrafficLight.GREEN  # no yellow during bootstrap


def test_baseline_p95_uses_only_success_runs() -> None:
    """Scenario: Baseline uses only successful runs for p95."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    records = [
        RunRecord(
            run_id=f"s{i}",
            environment_id="staging",
            profile_name="mobile_co",
            flow_name="checkout_full",
            duration_ms=ms,
            status=status,  # type: ignore[arg-type]
            created_at=base + timedelta(days=i),
        )
        for i, (ms, status) in enumerate(
            [(100, "success"), (200, "success"), (9_999, "failed"), (8_888, "error")]
        )
    ]
    # p95 over only the two success runs (100, 200) — failed/error ignored.
    assert calculate_p95(records) == 200
