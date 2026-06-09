"""End-to-end demo of the TestPilot SFCC wave-1 backend spine.

Walks the full API flow against the real app stack (auth, middlewares, routers,
EnvironmentResolver, RunOrchestrator, U3 reporter, U2 baseline) and prints the
resulting traffic-light verdict + Markdown report.

The Playwright executor is **stubbed** here (no live SFCC storefront — the
Akamai/Cloudflare IP exception, risk R1, is resolved before real runs). Everything
else is the production code path. AWS is not required (in-memory stores, D-U4-1).

Run:  .venv/Scripts/python.exe scripts/demo_e2e.py
"""

from __future__ import annotations

import os
import sys

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.services.environment_resolver import EnvironmentResolver
from src.api.services.live_status_tracker import LiveStatusTracker
from src.api.services.run_orchestrator import RunOrchestrator
from src.api.stores import (
    InMemoryEnvironmentStore,
    InMemoryRunReportStore,
    InMemorySecretsClient,
)
from src.api.services.environment_registry import EnvironmentRegistry
from src.baseline import BaselineManager, InMemoryBaselineStore
from src.models import (
    BrowserProfile,
    ExecutionReport,
    FlowName,
    FlowResult,
    ProfileResult,
    ResolvedEnvironment,
    StepResult,
    SyntheticUserConfig,
    TrafficLight,
)
from src.reporter import to_markdown

API_KEY = "demo-key"
H = {"X-API-Key": API_KEY}


async def _stub_executor(
    profile: BrowserProfile,
    flow_name: FlowName,
    config: SyntheticUserConfig,
    env: ResolvedEnvironment,
    run_id: str,
) -> ProfileResult:
    """Stand-in for src.executor.runner.run_profile (no real browser/storefront)."""
    steps = [
        StepResult(name="env_access_auth", status="success", duration_ms=1_200),
        StepResult(name="shopper_login", status="success", duration_ms=4_500),
        StepResult(name="search_product", status="success", duration_ms=3_000),
        StepResult(name="add_to_cart", status="success", duration_ms=2_500),
        StepResult(
            name="payment_failure_validation",
            status="success",
            duration_ms=3_200,
            screenshot_state="final",
        ),
    ]
    return ProfileResult(
        profile=profile,
        flow_result=FlowResult(
            flow_name=flow_name,
            status="success",
            steps=steps,
            duration_ms=sum(s.duration_ms for s in steps),
            orders_created=0,
        ),
        traffic_light=TrafficLight.GREEN,  # placeholder — U3 computes the real verdict
    )


def _build_client() -> TestClient:
    env_store = InMemoryEnvironmentStore()
    secrets = InMemorySecretsClient()
    secrets.set("sm/staging/env", {"username": "infra", "password": "***"})
    secrets.set(
        "sm/staging/shopper",
        {"username": "shopper@testpilot.internal", "password": "***"},
    )
    resolver = EnvironmentResolver(env_store, secrets)
    baseline = BaselineManager(InMemoryBaselineStore())
    reports = InMemoryRunReportStore()
    tracker = LiveStatusTracker()
    orchestrator = RunOrchestrator(
        resolver, baseline, reports, tracker, run_profile=_stub_executor
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


def _step(title: str) -> None:
    print(f"\n{'=' * 70}\n  {title}\n{'=' * 70}")


def main() -> None:
    # The Markdown report uses 🟢/🟡/🔴 — force UTF-8 so Windows cp1252 consoles work.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    os.environ["API_KEY"] = API_KEY
    client = _build_client()

    _step("1. Register the staging environment  (POST /v1/environments)")
    resp = client.post(
        "/v1/environments",
        headers=H,
        json={
            "environment_id": "staging",
            "store_url": "https://staging.example.shop",
            "env_access_secret_path": "sm/staging/env",
            "shopper_secret_path": "sm/staging/shopper",
            "active": True,
        },
    )
    print(f"  -> {resp.status_code}  {resp.json()['environment_id']} registered")

    _step("2. Launch a gate run  (POST /v1/run)")
    payload = {
        "schema_version": "v2",
        "environment_id": "staging",
        "flows": ["checkout_full"],
        "mode": "gate",
        "profiles": ["mobile_co", "desktop_co"],
        "products": [{"search_term": "camisa roja", "validate_variant": True}],
    }
    resp = client.post("/v1/run", headers=H, json=payload)
    report = resp.json()
    run_id = report["run_id"]
    print(f"  -> {resp.status_code}  X-Run-Id={resp.headers['X-Run-Id']}")
    print(f"  -> traffic_light={report['traffic_light']}  "
          f"bootstrap_mode={report['bootstrap_mode']}  "
          f"profiles={len(report['profile_results'])}")
    print(f"  -> orders_created published in JSON? "
          f"{'orders_created' in report}  (must be False — zero-contamination)")

    _step("3. Live status  (GET /v1/runs/{id}/status)")
    resp = client.get(f"/v1/runs/{run_id}/status", headers=H)
    status = resp.json()
    print(f"  -> state={status['state']}  orders_created={status['orders_created']}")

    _step("4. Fetch the full report  (GET /v1/runs/{id})")
    resp = client.get(f"/v1/runs/{run_id}", headers=H)
    print(f"  -> {resp.status_code}  schema-valid ExecutionReport for {run_id}")

    _step("5. Deploy-gate decision  (GET /v1/runs/latest, gate-only)")
    resp = client.get("/v1/runs/latest", headers=H)
    latest = resp.json()
    print(f"  -> verdict={latest['report']['traffic_light']}  "
          f"age_seconds={latest['age_seconds']}  ttl_ok={latest['ttl_ok']}")

    _step("6. History  (GET /v1/runs)")
    resp = client.get("/v1/runs", headers=H)
    listing = resp.json()
    print(f"  -> total={listing['total']}  items={len(listing['items'])}")

    _step("7. Human-readable Markdown report (reporter.to_markdown)")
    full = ExecutionReport.model_validate(
        client.get(f"/v1/runs/{run_id}", headers=H).json()
    )
    print(to_markdown(full))

    print("\nDemo OK — wave-1 backend spine works end to end "
          "(executor stubbed; AWS not required).")


if __name__ == "__main__":
    main()
