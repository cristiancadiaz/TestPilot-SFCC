"""Property-based tests for src/reporter (U3) — RNF-09.

Invariants that must hold for ANY valid run, regardless of profile/flow/status
mix:
- ``to_json_dict`` always validates against the v2 schema.
- ``to_markdown`` never raises and always mentions the global verdict.
- the global verdict is always the worst of the per-profile verdicts.

An empty baseline is used so success runs land in bootstrap (GREEN); failed/error
statuses drive YELLOW/RED — giving coverage across all three lights.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st
from jsonschema import Draft202012Validator

from src.baseline import BaselineManager, InMemoryBaselineStore
from src.models import (
    BrowserProfile,
    FlowResult,
    ProfileResult,
    StepResult,
    TrafficLight,
)
from src.reporter import generate_report, to_json_dict, to_markdown
from src.reporter.report_generator import _global_verdict

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "specs" / "execution_report.schema.json"
)
_VALIDATOR = Draft202012Validator(
    json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
)

_RUN_ID = "550e8400-e29b-41d4-a716-446655440000"
_START = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

_FLOWS = [
    "checkout_full",
    "checkout_card_declined",
    "search_and_filter",
    "browse_discounted_products",
    "pdp_validation",
    "cart_review",
]
_PROFILES = ["mobile_co", "desktop_co", "desktop_ec"]
_STATUSES = ["success", "failed", "error"]


def _profile(name: str) -> BrowserProfile:
    return BrowserProfile(
        name=name,  # type: ignore[arg-type]
        viewport_width=390,
        viewport_height=844,
        locale="es-CO",
        user_agent="Mozilla/5.0 (compatible; TestPilot/1.0) AppleWebKit/605.1.15",
        is_mobile=True,
    )


_combo = st.tuples(
    st.sampled_from(_PROFILES),
    st.sampled_from(_FLOWS),
    st.sampled_from(_STATUSES),
    st.integers(min_value=0, max_value=600_000),
)


@settings(max_examples=150)
@given(st.lists(_combo, min_size=1, max_size=3))
def test_report_is_always_schema_valid_and_consistent(
    combos: list[tuple[str, str, str, int]],
) -> None:
    profile_results: list[ProfileResult] = []
    for profile_name, flow_name, status, duration in combos:
        step_status = "success" if status == "success" else "failed"
        flow_result = FlowResult(
            flow_name=flow_name,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            steps=[
                StepResult(
                    name="step",
                    status=step_status,  # type: ignore[arg-type]
                    duration_ms=duration,
                )
            ],
            duration_ms=duration,
            orders_created=0,
        )
        profile_results.append(
            ProfileResult(
                profile=_profile(profile_name),
                flow_result=flow_result,
                traffic_light=TrafficLight.GREEN,
            )
        )

    manager = BaselineManager(InMemoryBaselineStore())  # empty -> success = bootstrap
    report = generate_report(
        run_id=_RUN_ID,
        environment_id="staging",
        mode="gate",
        started_at=_START,
        finished_at=_START + timedelta(minutes=5),
        profile_results=profile_results,
        baseline_manager=manager,
    )

    # 1. JSON always validates against the contract.
    _VALIDATOR.validate(to_json_dict(report))

    # 2. Markdown never raises and mentions the verdict.
    md = to_markdown(report)
    assert report.traffic_light.value.upper() in md

    # 3. Global verdict is the worst of the per-profile verdicts.
    expected = _global_verdict([pr.traffic_light for pr in report.profile_results])
    assert report.traffic_light == expected

    # 4. orders_created never published.
    assert "orders_created" not in to_json_dict(report)
