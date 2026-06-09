"""SFRA controller timing aggregation (U7, RF-23).

Groups captured requests by the SFRA ``Controller-Action`` they hit (e.g.
``Product-Show``, ``Cart-AddProduct``) and reports count + p95 latency per
controller — the "controller waterfall". Asset and non-controller requests
(``.js``/``.css``/images) are excluded. The p95 uses the same ceiling-index
method as U2's ``calculate_p95`` so the numbers are consistent across modules.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING

from src.models import ControllerTiming

if TYPE_CHECKING:
    from src.executor.network_capture import RequestRecord

# Documented SFRA controller families (for reference / readability).
SFRA_CONTROLLER_PATTERNS: tuple[str, ...] = (
    r"\w+-Show",
    r"Cart-\w+",
    r"CheckoutServices-\w+",
    r"CheckoutShippingServices-\w+",
    r"Search-\w+",
    r"Product-\w+",
    r"Account-\w+",
)

# A SFRA controller appears in the path as `Controller-Action` (PascalCase pair).
_CONTROLLER_RE = re.compile(r"/([A-Z][A-Za-z0-9]*-[A-Za-z][A-Za-z0-9]+)(?=[/?#]|$)")


def extract_controller(url: str) -> str | None:
    """Return the SFRA ``Controller-Action`` in *url*'s path, or ``None``."""
    match = _CONTROLLER_RE.search(url)
    return match.group(1) if match else None


def _p95(durations: list[int]) -> int:
    """p95 over *durations* — ceiling index, identical to U2's ``calculate_p95``."""
    if not durations:
        return 0
    ordered = sorted(durations)
    index = math.ceil(0.95 * len(ordered)) - 1
    return int(ordered[index])


def aggregate_controllers(
    records: "list[RequestRecord]",
) -> list[ControllerTiming]:
    """Aggregate *records* by SFRA controller → count + p95 (slowest first)."""
    buckets: dict[str, list[int]] = {}
    for rec in records:
        controller = extract_controller(rec.url)
        if controller is None:
            continue  # asset / non-controller — excluded
        buckets.setdefault(controller, []).append(rec.duration_ms)

    timings = [
        ControllerTiming(pattern=pattern, count=len(durations), p95_ms=_p95(durations))
        for pattern, durations in buckets.items()
    ]
    timings.sort(key=lambda t: (-t.p95_ms, t.pattern))
    return timings
