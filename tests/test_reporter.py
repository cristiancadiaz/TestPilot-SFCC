"""Deterministic tests for src/reporter/report_generator.py (U3).

Covers the verdict matrix (green/yellow/red/bootstrap, functional vs infra
failure, global worst-of), JSON schema validation against
``specs/execution_report.schema.json`` v2, and the zero-contamination invariant
(BR-U3-01). No LLM, no network — everything is deterministic.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import pytest
from jsonschema import Draft202012Validator

from src.baseline import BaselineManager, InMemoryBaselineStore
from src.models import (
    BrowserProfile,
    EnvironmentId,
    FlowName,
    FlowResult,
    ProfileId,
    ProfileResult,
    RunRecord,
    StepResult,
    TrafficLight,
)
from src.reporter import generate_report, to_json_dict, to_markdown
from src.reporter.report_generator import _global_verdict, compute_profile_verdict

# ---------------------------------------------------------------------------
# Schema validator (loaded once)
# ---------------------------------------------------------------------------

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "specs" / "execution_report.schema.json"
)
_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
_VALIDATOR = Draft202012Validator(_SCHEMA)

_RUN_ID = "550e8400-e29b-41d4-a716-446655440000"
_START = datetime(2026, 5, 27, 10, 0, 0, tzinfo=timezone.utc)
_FINISH = _START + timedelta(minutes=8, seconds=30)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _profile(name: ProfileId = "mobile_co") -> BrowserProfile:
    return BrowserProfile(
        name=name,
        viewport_width=390,
        viewport_height=844,
        locale="es-CO",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        is_mobile=True,
    )


def _profile_result(
    status: Literal["success", "failed", "error"],
    duration_ms: int,
    *,
    profile_name: ProfileId = "mobile_co",
    flow_name: FlowName = "checkout_full",
) -> ProfileResult:
    """A ProfileResult with the U1 GREEN placeholder verdict."""
    step_status: Literal["success", "failed"] = (
        "success" if status == "success" else "failed"
    )
    flow_result = FlowResult(
        flow_name=flow_name,
        status=status,
        steps=[
            StepResult(
                name="final_step",
                status=step_status,
                duration_ms=duration_ms,
                screenshot_state="final" if status == "success" else "fail",
            )
        ],
        duration_ms=duration_ms,
        orders_created=0,
    )
    return ProfileResult(
        profile=_profile(profile_name),
        flow_result=flow_result,
        traffic_light=TrafficLight.GREEN,  # placeholder from U1
    )


def _seed_baseline(
    manager: BaselineManager,
    *,
    n_success: int,
    duration_ms: int,
    environment_id: EnvironmentId = "staging",
    profile_name: ProfileId = "mobile_co",
    flow_name: FlowName = "checkout_full",
) -> None:
    """Seed *n_success* gate-mode success runs so p95 == duration_ms."""
    for i in range(n_success):
        manager.save_run(
            RunRecord(
                run_id=f"seed-{i}",
                environment_id=environment_id,
                profile_name=profile_name,
                flow_name=flow_name,
                duration_ms=duration_ms,
                status="success",
                created_at=_START - timedelta(days=n_success - i),
            ),
            mode="gate",
        )


def _make_manager() -> BaselineManager:
    return BaselineManager(InMemoryBaselineStore())


def _report(profile_results: list[ProfileResult], manager: BaselineManager) -> Any:
    return generate_report(
        run_id=_RUN_ID,
        environment_id="staging",
        mode="gate",
        started_at=_START,
        finished_at=_FINISH,
        profile_results=profile_results,
        baseline_manager=manager,
    )


# ---------------------------------------------------------------------------
# Verdict matrix — per profile×flow
# ---------------------------------------------------------------------------


def test_success_fast_is_green() -> None:
    manager = _make_manager()
    _seed_baseline(manager, n_success=14, duration_ms=100_000)  # p95=100k, not bootstrap
    report = _report([_profile_result("success", 100_000)], manager)
    assert report.profile_results[0].traffic_light == TrafficLight.GREEN
    assert report.traffic_light == TrafficLight.GREEN


def test_success_slow_is_yellow() -> None:
    manager = _make_manager()
    _seed_baseline(manager, n_success=14, duration_ms=100_000)
    # ratio 1.3 -> YELLOW (>= 1.2, < 1.5)
    report = _report([_profile_result("success", 130_000)], manager)
    assert report.profile_results[0].traffic_light == TrafficLight.YELLOW


def test_success_very_slow_is_red() -> None:
    manager = _make_manager()
    _seed_baseline(manager, n_success=14, duration_ms=100_000)
    # ratio 1.6 -> RED (>= 1.5)
    report = _report([_profile_result("success", 160_000)], manager)
    assert report.profile_results[0].traffic_light == TrafficLight.RED


def test_failed_status_is_red_regardless_of_timing() -> None:
    manager = _make_manager()
    _seed_baseline(manager, n_success=14, duration_ms=100_000)
    report = _report([_profile_result("failed", 90_000)], manager)  # fast but failed
    assert report.profile_results[0].traffic_light == TrafficLight.RED


def test_error_status_is_yellow() -> None:
    manager = _make_manager()
    _seed_baseline(manager, n_success=14, duration_ms=100_000)
    report = _report([_profile_result("error", 0)], manager)
    assert report.profile_results[0].traffic_light == TrafficLight.YELLOW


def test_bootstrap_never_yellow_even_when_slow() -> None:
    manager = _make_manager()
    _seed_baseline(manager, n_success=5, duration_ms=100_000)  # < 14 -> bootstrap
    report = _report([_profile_result("success", 999_999)], manager)
    assert report.profile_results[0].traffic_light == TrafficLight.GREEN
    assert report.bootstrap_mode is True


# ---------------------------------------------------------------------------
# Global verdict = worst-of
# ---------------------------------------------------------------------------


def test_global_is_worst_of_profiles() -> None:
    manager = _make_manager()
    # desktop_co will be RED (failed); mobile_co GREEN (bootstrap); desktop_ec YELLOW
    _seed_baseline(manager, n_success=14, duration_ms=100_000, profile_name="desktop_ec")
    report = _report(
        [
            _profile_result("success", 50_000, profile_name="mobile_co"),
            _profile_result("failed", 50_000, profile_name="desktop_co"),
            _profile_result("success", 130_000, profile_name="desktop_ec"),
        ],
        manager,
    )
    verdicts = {pr.profile.name: pr.traffic_light for pr in report.profile_results}
    assert verdicts["desktop_co"] == TrafficLight.RED
    assert verdicts["desktop_ec"] == TrafficLight.YELLOW
    assert report.traffic_light == TrafficLight.RED  # worst-of


def test_global_verdict_helper() -> None:
    assert _global_verdict([TrafficLight.GREEN, TrafficLight.YELLOW]) == TrafficLight.YELLOW
    assert _global_verdict([TrafficLight.YELLOW, TrafficLight.RED]) == TrafficLight.RED
    assert _global_verdict([TrafficLight.GREEN]) == TrafficLight.GREEN
    assert _global_verdict([]) == TrafficLight.GREEN


# ---------------------------------------------------------------------------
# JSON schema validation (Gate 4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "duration", "n_success"),
    [
        ("success", 100_000, 14),  # green
        ("success", 130_000, 14),  # yellow
        ("success", 160_000, 14),  # red
        ("success", 100_000, 5),   # bootstrap
        ("failed", 50_000, 14),    # functional failure
        ("error", 0, 14),          # infra error
    ],
)
def test_json_dict_validates_against_schema(
    status: Literal["success", "failed", "error"],
    duration: int,
    n_success: int,
) -> None:
    manager = _make_manager()
    if status == "success":
        _seed_baseline(manager, n_success=n_success, duration_ms=100_000)
    report = _report([_profile_result(status, duration)], manager)
    payload = to_json_dict(report)
    _VALIDATOR.validate(payload)  # raises if invalid


def test_multi_profile_json_validates() -> None:
    manager = _make_manager()
    report = _report(
        [
            _profile_result("success", 50_000, profile_name="mobile_co"),
            _profile_result("failed", 50_000, profile_name="desktop_co"),
        ],
        manager,
    )
    _VALIDATOR.validate(to_json_dict(report))


def test_orders_created_absent_from_json_but_invariant_holds() -> None:
    manager = _make_manager()
    report = _report([_profile_result("success", 50_000)], manager)
    payload = to_json_dict(report)
    assert "orders_created" not in payload
    assert "orders_created" not in payload["profile_results"][0]["flow_result"]
    assert report.orders_created == 0


# ---------------------------------------------------------------------------
# Zero-contamination assert (BR-U3-01)
# ---------------------------------------------------------------------------


def test_generate_report_rejects_contaminated_flow() -> None:
    manager = _make_manager()
    profile_result = _profile_result("success", 50_000)
    # Bypass Pydantic to inject a bad value and exercise the assert guard.
    object.__setattr__(profile_result.flow_result, "orders_created", 1)
    with pytest.raises(AssertionError, match="Zero-contamination violated"):
        _report([profile_result], manager)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def test_markdown_contains_verdict_and_invariant_line() -> None:
    manager = _make_manager()
    _seed_baseline(manager, n_success=14, duration_ms=100_000)
    report = _report([_profile_result("success", 160_000)], manager)  # RED
    md = to_markdown(report)
    assert "RED" in md
    assert "orders_created:** 0" in md
    assert "checkout_full" in md
    assert "mobile_co" in md


# ---------------------------------------------------------------------------
# No cross-environment baseline mixing
# ---------------------------------------------------------------------------


def test_baseline_queried_with_run_environment() -> None:
    """A staging run must not borrow a sandbox baseline (compound-key isolation)."""
    manager = _make_manager()
    # Seed history under SANDBOX only; the run targets STAGING.
    _seed_baseline(
        manager, n_success=14, duration_ms=100_000, environment_id="sandbox"
    )
    report = _report([_profile_result("success", 999_999)], manager)
    # Staging has no history -> bootstrap -> GREEN despite the huge duration.
    assert report.profile_results[0].traffic_light == TrafficLight.GREEN
    assert report.bootstrap_mode is True


# ---------------------------------------------------------------------------
# compute_profile_verdict direct unit (pure function)
# ---------------------------------------------------------------------------


def test_compute_profile_verdict_pure() -> None:
    from src.models import BaselineComparison

    fast = FlowResult(
        flow_name="cart_review",
        status="success",
        steps=[StepResult(name="s", status="success", duration_ms=10)],
        duration_ms=100,
    )
    bc = BaselineComparison(p95_ms=100, current_ms=100, bootstrap_mode=False, runs_count=14)
    assert compute_profile_verdict(fast, bc) == TrafficLight.GREEN
