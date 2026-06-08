"""Report generator for TestPilot SFCC — U3 core module.

Turns the raw execution outputs into the published ``ExecutionReport``:

- Computes the **deterministic** traffic light per profile×flow and globally.
  The verdict is 100% rule-based (p95 baseline) — no LLM, ever (P7 / C10 /
  invariant #8). The audit agent (U6) can never move this verdict.
- Serializes the report to a schema-valid JSON dict (snake_case — the v2 schema
  and ``ExecutionReport`` already agree on field names; ``orders_created`` is
  excluded from the contract, BR-U3-01).
- Renders a human-readable Markdown report.

Boundary: U3 only **reads** the baseline (``get_baseline_comparison``). Persisting
the current run (``BaselineManager.save_run``) is U4's orchestration job
(decision D-U3-3) — the reporter never writes to the baseline (CLAUDE.md boundary).

Out of scope (deferred; the v2 schema permits their absence): the ``audit`` object
(U6) and per-profile ``network_summary`` (U7).

Traceability: RF-09 (deterministic verdict), schema ``execution_report`` v2,
BR-U3-01 (zero contamination), Gate 4 of build-sequence.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.baseline import BaselineManager, compute_traffic_light
from src.models import (
    BaselineComparison,
    EnvironmentId,
    ExecutionReport,
    FlowResult,
    Mode,
    ProfileResult,
    TrafficLight,
)

# Worst-of ordering for aggregating the global verdict (RED beats YELLOW beats GREEN).
_VERDICT_RANK: dict[TrafficLight, int] = {
    TrafficLight.GREEN: 0,
    TrafficLight.YELLOW: 1,
    TrafficLight.RED: 2,
}

_VERDICT_EMOJI: dict[TrafficLight, str] = {
    TrafficLight.GREEN: "🟢",
    TrafficLight.YELLOW: "🟡",
    TrafficLight.RED: "🔴",
}


# ---------------------------------------------------------------------------
# Deterministic verdict rules (pure — no I/O, no LLM)
# ---------------------------------------------------------------------------


def compute_profile_verdict(
    flow_result: FlowResult,
    baseline: BaselineComparison,
) -> TrafficLight:
    """Return the deterministic traffic light for one profile×flow result.

    Rules (applied in order):
    1. ``status == "failed"`` -> RED    (functional failure of the storefront)
    2. ``status == "error"``  -> YELLOW (infrastructure error — Playwright/DNS/net)
    3. ``status == "success"`` -> the p95 rule (``compute_traffic_light``, U2):
       bootstrap or no baseline -> GREEN; else GREEN/YELLOW/RED by the p95 ratio.

    This is the only place a per-profile verdict is decided. It is pure and
    contains no LLM calls (P7 / C10).
    """
    if flow_result.status == "failed":
        return TrafficLight.RED
    if flow_result.status == "error":
        return TrafficLight.YELLOW
    return compute_traffic_light(
        current_ms=flow_result.duration_ms,
        p95_ms=baseline.p95_ms,
        bootstrap=baseline.bootstrap_mode,
    )


def _global_verdict(verdicts: list[TrafficLight]) -> TrafficLight:
    """Return the worst verdict across all profile×flow combinations."""
    worst = TrafficLight.GREEN
    for verdict in verdicts:
        if _VERDICT_RANK[verdict] > _VERDICT_RANK[worst]:
            worst = verdict
    return worst


def _report_bootstrap(comparisons: list[BaselineComparison]) -> bool:
    """Report-level bootstrap flag (D-U3-2: True iff *all* combos are bootstrap).

    Informational only — the dashboard shows a "calibrating" badge. It never
    changes a per-profile verdict; each combo already applies bootstrap silence
    individually inside ``compute_traffic_light``.
    """
    if not comparisons:
        return False
    return all(c.bootstrap_mode for c in comparisons)


def _ratio(comparison: BaselineComparison) -> float:
    """Slowdown ratio; 0.0 when there is no usable p95 (bootstrap / no history)."""
    if comparison.p95_ms == 0:
        return 0.0
    return comparison.current_ms / comparison.p95_ms


def _select_report_baseline(
    comparisons: list[BaselineComparison],
    verdicts: list[TrafficLight],
    global_verdict: TrafficLight,
) -> BaselineComparison | None:
    """Pick the single report-level ``baseline_comparison`` (D-U3-1).

    The v2 report has one comparison but a run can span N combos. Return the
    comparison of the combo that *drove the global verdict* (worst light;
    tie-break = highest slowdown ratio). Return ``None`` when no combo has usable
    history (all bootstrap or no baseline).
    """
    if not comparisons or all(
        c.bootstrap_mode or c.p95_ms == 0 for c in comparisons
    ):
        return None
    candidates = [
        c for c, v in zip(comparisons, verdicts) if v == global_verdict
    ] or comparisons
    return max(candidates, key=_ratio)


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def generate_report(
    run_id: str,
    environment_id: EnvironmentId,
    mode: Mode,
    started_at: datetime,
    finished_at: datetime,
    profile_results: list[ProfileResult],
    baseline_manager: BaselineManager,
) -> ExecutionReport:
    """Assemble the ``ExecutionReport`` and compute the deterministic verdict.

    The incoming ``profile_results`` come from U1 with a ``GREEN`` placeholder
    traffic light; this function replaces each with the real p95-based verdict.

    Args:
        run_id:          UUID of the run (generated by the orchestrator, U4).
        environment_id:  Target SFCC environment of the run.
        mode:            ``"gate"`` or ``"exploratory"``.
        started_at:      Run start timestamp.
        finished_at:     Run finish timestamp.
        profile_results: Per profile×flow results from the executor (U1).
        baseline_manager: Read-only baseline access (U2); never written here.

    Returns:
        A fully-populated ``ExecutionReport`` ready for ``to_json_dict`` /
        ``to_markdown``.
    """
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    if duration_ms < 0:  # guard against clock skew; the schema requires >= 0
        duration_ms = 0

    resolved: list[ProfileResult] = []
    comparisons: list[BaselineComparison] = []
    verdicts: list[TrafficLight] = []

    for profile_result in profile_results:
        flow_result = profile_result.flow_result
        # BR-U3-01 / invariant #1: zero contamination — never relaxed.
        assert flow_result.orders_created == 0, (
            "Zero-contamination violated in generate_report: "
            f"flow={flow_result.flow_name} "
            f"orders_created={flow_result.orders_created}"
        )
        comparison = baseline_manager.get_baseline_comparison(
            environment_id,
            profile_result.profile.name,
            flow_result.flow_name,
            flow_result.duration_ms,
        )
        verdict = compute_profile_verdict(flow_result, comparison)
        resolved.append(
            ProfileResult(
                profile=profile_result.profile,
                flow_result=flow_result,
                traffic_light=verdict,
            )
        )
        comparisons.append(comparison)
        verdicts.append(verdict)

    global_verdict = _global_verdict(verdicts)
    report = ExecutionReport(
        run_id=run_id,
        environment_id=environment_id,
        mode=mode,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        traffic_light=global_verdict,
        bootstrap_mode=_report_bootstrap(comparisons),
        profile_results=resolved,
        baseline_comparison=_select_report_baseline(
            comparisons, verdicts, global_verdict
        ),
    )
    # The report never publishes orders_created, but the invariant still holds.
    assert report.orders_created == 0
    return report


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def to_json_dict(report: ExecutionReport) -> dict[str, Any]:
    """Serialize *report* to a schema-valid JSON dict.

    ``model_dump(mode="json")`` yields ISO-8601 datetimes and string enum values;
    ``orders_created`` is excluded by the model (BR-U3-01). The keys are
    snake_case and match ``specs/execution_report.schema.json`` v2 exactly — no
    remapping is needed (the earlier plan's "camelCase" note was incorrect).
    """
    return report.model_dump(mode="json")


def to_markdown(report: ExecutionReport) -> str:
    """Render *report* as human-readable Markdown (legible for non-technical users)."""
    verdict = report.traffic_light
    lines: list[str] = [
        f"# TestPilot Report — {_VERDICT_EMOJI[verdict]} {verdict.value.upper()}",
        "",
        f"- **Run ID:** `{report.run_id}`",
        f"- **Environment:** {report.environment_id}",
        f"- **Mode:** {report.mode}",
        f"- **Started:** {report.started_at.isoformat()}",
        f"- **Finished:** {report.finished_at.isoformat()}",
        f"- **Duration:** {report.duration_ms} ms",
    ]
    if report.bootstrap_mode:
        lines.append(
            "- **Bootstrap:** calibrating baseline — no p95 yellow alerts yet "
            "(invariant #4)"
        )
    baseline = report.baseline_comparison
    if baseline is not None:
        lines.append(
            f"- **Baseline p95:** {baseline.p95_ms} ms vs current "
            f"{baseline.current_ms} ms ({baseline.runs_count} runs)"
        )
    # BR-U3-01: the JSON omits orders_created; the Markdown documents the invariant.
    lines.append(
        f"- **orders_created:** {report.orders_created} ✓ (zero-contamination)"
    )
    lines.append("")

    for profile_result in report.profile_results:
        flow_result = profile_result.flow_result
        profile_verdict = profile_result.traffic_light
        lines.append(
            f"## {_VERDICT_EMOJI[profile_verdict]} "
            f"{profile_result.profile.name} · {flow_result.flow_name} "
            f"— {flow_result.status}"
        )
        lines.append("")
        lines.append("| Step | Phase | Status | Duration (ms) | Evidence | Error |")
        lines.append("|---|---|---|---:|---|---|")
        for step in flow_result.steps:
            state = step.screenshot_state or "—"
            error = (step.error or "—").replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {step.name} | {step.phase} | {step.status} | "
                f"{step.duration_ms} | {state} | {error} |"
            )
        lines.append("")

    return "\n".join(lines)
