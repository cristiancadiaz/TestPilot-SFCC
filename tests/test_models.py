"""Tests for src/models.py — construction + invariants against specs/ v2 (RF-02).

Each schema constraint (enum, min/max, uniqueItems, const, defaults) has at least
one invalid-case test. The 4 embedded examples of the real schema are round-tripped
against the model so the contract and the model can never silently diverge.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from pydantic import ValidationError

from src.models import (
    BaselineComparison,
    BrowserProfile,
    ExecutionReport,
    FlowResult,
    Product,
    ProfileResult,
    RunOptions,
    RunRecord,
    StepResult,
    SyntheticUserConfig,
    TrafficLight,
)

SCHEMA_PATH = pathlib.Path(__file__).resolve().parents[1] / "specs" / "synthetic-user-config.schema.json"


def _config(**overrides: object) -> SyntheticUserConfig:
    """Build a valid SyntheticUserConfig, overriding fields per test."""
    base: dict[str, object] = {
        "schema_version": "v2",
        "environment_id": "staging",
        "flows": ["checkout_full"],
        "profiles": ["mobile_co"],
        "products": [{"search_term": "camisa roja"}],
    }
    base.update(overrides)
    return SyntheticUserConfig(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------------
# SyntheticUserConfig — request contract
# --------------------------------------------------------------------------------


def test_synthetic_user_config_valid() -> None:
    cfg = _config(
        flows=["checkout_full", "search_and_filter"],
        profiles=["mobile_co", "desktop_co"],
        products=[{"search_term": "jeans azul", "validate_variant": False}],
    )
    assert cfg.flows == ["checkout_full", "search_and_filter"]
    assert cfg.profiles == ["mobile_co", "desktop_co"]
    assert cfg.products[0].validate_variant is False


def test_synthetic_user_config_schema_version_v2() -> None:
    assert _config().schema_version == "v2"
    with pytest.raises(ValidationError):
        _config(schema_version="v1")


def test_synthetic_user_config_rejects_production() -> None:
    # Invariant: never production.
    with pytest.raises(ValidationError):
        _config(environment_id="production")


def test_synthetic_user_config_invalid_flow() -> None:
    with pytest.raises(ValidationError):
        _config(flows=["definitely_not_a_flow"])


def test_synthetic_user_config_accepts_journey_flows() -> None:
    # Closed catalog v2: the 4 journey flows + full_journey composition alias.
    journey = ["search_and_filter", "browse_discounted_products", "pdp_validation", "cart_review"]
    assert _config(flows=journey).flows == journey
    assert _config(flows=["full_journey"]).flows == ["full_journey"]


def test_synthetic_user_config_mode() -> None:
    assert _config().mode == "gate"  # default
    assert _config(mode="exploratory").mode == "exploratory"
    with pytest.raises(ValidationError):
        _config(mode="turbo")


def test_synthetic_user_config_invalid_profile() -> None:
    with pytest.raises(ValidationError):
        _config(profiles=["desktop_mx"])


def test_synthetic_user_config_flows_bounds() -> None:
    with pytest.raises(ValidationError):
        _config(flows=[])
    with pytest.raises(ValidationError):
        # 7 items > maxItems 6 (all distinct, so it fails on bounds not uniqueness).
        _config(
            flows=[
                "checkout_full",
                "checkout_card_declined",
                "search_and_filter",
                "browse_discounted_products",
                "pdp_validation",
                "cart_review",
                "full_journey",
            ]
        )
    with pytest.raises(ValidationError):
        _config(flows=["checkout_full", "checkout_full"])  # duplicates


def test_synthetic_user_config_profiles_bounds() -> None:
    with pytest.raises(ValidationError):
        _config(profiles=[])
    with pytest.raises(ValidationError):
        _config(profiles=["mobile_co", "desktop_co", "desktop_ec", "mobile_co"])  # >3 and dup
    with pytest.raises(ValidationError):
        _config(profiles=["mobile_co", "mobile_co"])  # duplicates


def test_synthetic_user_config_products_bounds() -> None:
    with pytest.raises(ValidationError):
        _config(products=[])
    with pytest.raises(ValidationError):
        _config(products=[{"search_term": f"item {i}"} for i in range(11)])  # >10
    with pytest.raises(ValidationError):
        _config(products=[{"search_term": "x"}])  # search_term < 2 chars


def test_schema_examples_instantiate() -> None:
    # Round-trip the real embedded examples against the model — contract fidelity.
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    examples = schema["examples"]
    assert len(examples) == 4
    for example in examples:
        cfg = SyntheticUserConfig(**example)
        assert cfg.schema_version == "v2"


# --------------------------------------------------------------------------------
# RunOptions / Product — defaults + cost invariant
# --------------------------------------------------------------------------------


def test_run_options_screenshots_must_be_false() -> None:
    # Cost invariant (ADR-003): capture_intermediate_screenshots is const false.
    assert RunOptions().capture_intermediate_screenshots is False
    with pytest.raises(ValidationError):
        RunOptions(capture_intermediate_screenshots=True)  # type: ignore[arg-type]


def test_run_options_defaults() -> None:
    assert RunOptions().timeout_seconds == 180
    assert Product(search_term="camisa").validate_variant is True


# --------------------------------------------------------------------------------
# Result models — invariants + construction
# --------------------------------------------------------------------------------


def _flow_result(**overrides: object) -> FlowResult:
    base: dict[str, object] = {
        "flow_name": "checkout_full",
        "status": "success",
        "duration_ms": 1000,
        "steps": [{"name": "final", "status": "success", "duration_ms": 10}],
    }
    base.update(overrides)
    return FlowResult(**base)  # type: ignore[arg-type]


def test_flow_result_orders_created_default() -> None:
    fr = _flow_result()
    assert fr.orders_created == 0
    # Internal invariant field — never published in the JSON contract.
    assert "orders_created" not in fr.model_dump()


def test_execution_report_orders_created_default() -> None:
    profile = {
        "name": "mobile_co",
        "viewport_width": 390,
        "viewport_height": 844,
        "locale": "es-CO",
        "user_agent": "Mozilla/5.0 (iPhone) test",
        "is_mobile": True,
    }
    report = ExecutionReport(
        run_id="550e8400-e29b-41d4-a716-446655440000",
        environment_id="staging",
        mode="gate",
        started_at="2026-05-27T10:00:00Z",  # type: ignore[arg-type]
        finished_at="2026-05-27T10:08:30Z",  # type: ignore[arg-type]
        duration_ms=510000,
        traffic_light="green",  # type: ignore[arg-type]
        bootstrap_mode=False,
        profile_results=[
            ProfileResult(
                profile=BrowserProfile(**profile),  # type: ignore[arg-type]
                flow_result=_flow_result(),
                traffic_light="green",  # type: ignore[arg-type]
            )
        ],
    )
    assert report.orders_created == 0
    dump = report.model_dump()
    assert "orders_created" not in dump
    # Contract mirrors the schema field name (run_id, not test_run_id).
    assert "run_id" in dump and "test_run_id" not in dump


def test_traffic_light_values() -> None:
    assert TrafficLight.GREEN.value == "green"
    assert TrafficLight.YELLOW.value == "yellow"
    assert TrafficLight.RED.value == "red"
    assert {t.value for t in TrafficLight} == {"green", "yellow", "red"}


def test_browser_profile_valid() -> None:
    profile = BrowserProfile(
        name="desktop_ec",
        viewport_width=1280,
        viewport_height=800,
        locale="es-EC",
        user_agent="Mozilla/5.0 (X11; Linux x86_64) Chrome",
        is_mobile=False,
    )
    assert profile.name == "desktop_ec"
    assert profile.is_mobile is False
    with pytest.raises(ValidationError):
        BrowserProfile(
            name="desktop_ec",
            viewport_width=100,  # < 320
            viewport_height=800,
            locale="es-EC",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) Chrome",
            is_mobile=False,
        )


def test_run_record_valid() -> None:
    from datetime import UTC, datetime

    record = RunRecord(
        run_id="550e8400-e29b-41d4-a716-446655440000",
        environment_id="staging",
        profile_name="desktop_co",
        flow_name="search_and_filter",
        duration_ms=42000,
        status="success",
        created_at=datetime(2026, 5, 27, 10, 0, tzinfo=UTC),
    )
    assert record.created_at.tzinfo is not None  # timezone-aware
    assert record.flow_name == "search_and_filter"


def test_step_result_findings_evidence() -> None:
    # Findings-driven evidence (RF-26 / ADR-003): finding_dimension only with finding.
    step = StepResult(
        name="mini_cart_validation",
        status="success",
        duration_ms=3200,
        screenshot_state="finding",
        finding_dimension="commerce_integrity",
    )
    assert step.phase == "flow"  # default
    assert step.finding_dimension == "commerce_integrity"
    with pytest.raises(ValidationError):
        StepResult(name="x", status="success", duration_ms=10, screenshot_state="bogus")  # type: ignore[arg-type]


def test_baseline_comparison_valid() -> None:
    comparison = BaselineComparison(p95_ms=185000, current_ms=165000, bootstrap_mode=False, runs_count=18)
    assert comparison.p95_ms == 185000
    with pytest.raises(ValidationError):
        BaselineComparison(p95_ms=-1, current_ms=165000, bootstrap_mode=False, runs_count=18)


def test_resolved_environment_valid() -> None:
    from src.models import Credentials, ResolvedEnvironment

    env = ResolvedEnvironment(
        environment_id="staging",
        store_url="https://staging.example.com",
        env_access=Credentials(username="infra", password="s3cret"),
        shopper=Credentials(username="shopper@testpilot.internal", password="pw"),
    )
    assert env.environment_id == "staging"
    assert env.shopper.username.endswith("@testpilot.internal")


def test_resolved_environment_rejects_http() -> None:
    from src.models import Credentials, ResolvedEnvironment

    with pytest.raises(ValidationError):
        ResolvedEnvironment(
            environment_id="staging",
            store_url="http://insecure.example.com",  # not https
            env_access=Credentials(username="infra", password="s3cret"),
            shopper=Credentials(username="s@testpilot.internal", password="pw"),
        )


def test_credentials_password_not_in_repr() -> None:
    # RNF-03 zero-secret logging: password must never appear in repr()/logs.
    from src.models import Credentials

    creds = Credentials(username="infra", password="topsecret")
    assert "topsecret" not in repr(creds)
    assert "infra" in repr(creds)
