"""Baseline manager for TestPilot SFCC.

Public API of the src/baseline package. U3 (reporter) and U4 (API) import from
here — never from src.baseline.baseline_manager directly.

Only gate-mode runs feed the baseline (C11 / invariant #5).
The traffic light is computed deterministically (P7 / C10).
"""

from src.baseline.baseline_manager import (
    BASELINE_WINDOW,
    BOOTSTRAP_MIN_RUNS,
    RED_THRESHOLD,
    YELLOW_THRESHOLD,
    BaselineManager,
    BaselineStore,
    InMemoryBaselineStore,
    calculate_p95,
    compute_traffic_light,
    is_bootstrap_mode,
)

__all__ = [
    "BaselineStore",
    "InMemoryBaselineStore",
    "BaselineManager",
    "calculate_p95",
    "is_bootstrap_mode",
    "compute_traffic_light",
    "YELLOW_THRESHOLD",
    "RED_THRESHOLD",
    "BOOTSTRAP_MIN_RUNS",
    "BASELINE_WINDOW",
]
