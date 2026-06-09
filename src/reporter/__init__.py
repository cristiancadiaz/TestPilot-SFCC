"""Reporter package for TestPilot SFCC — U3.

Public API. U4 (API) imports from ``src.reporter`` only, never from
``src.reporter.report_generator`` directly.

The traffic light produced here is computed EXCLUSIVELY by the deterministic p95
rule (P7 / C10 / invariant #8) — there are no LLM calls in this package.
"""

from src.reporter.report_generator import (
    compute_profile_verdict,
    generate_report,
    to_json_dict,
    to_markdown,
)

__all__ = [
    "generate_report",
    "compute_profile_verdict",
    "to_json_dict",
    "to_markdown",
]
