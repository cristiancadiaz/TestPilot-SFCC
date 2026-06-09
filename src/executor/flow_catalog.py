"""Closed flow catalog + full_journey composition (U5, invariant #2).

Single source of truth for the closed flow catalog. ``runner.py`` and the U4
orchestrator import the registry from here — the catalog grows ONLY via curated PR.

``full_journey`` is a **composition alias**, never a flow file (D15): it is expanded
to its declared modular sequence by ``expand_flows`` *before* the executor ever runs.
``critical_points`` feed ADR-003 evidence (U6 audit) — declared, not yet consumed here.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from src.executor.flows import (
    browse_discounted_products,
    cart_review,
    checkout_card_declined,
    checkout_full,
    pdp_validation,
    search_and_filter,
)
from src.models import (
    FlowName,
    FlowResult,
    FlowSelection,
    ResolvedEnvironment,
    SyntheticUserConfig,
)

if TYPE_CHECKING:
    from playwright.async_api import Page

FlowCoro = Callable[
    ["Page", SyntheticUserConfig, ResolvedEnvironment, str, str],
    Coroutine[Any, Any, FlowResult],
]


@dataclass(frozen=True)
class FlowSpec:
    """Catalog entry: the flow's run coroutine + its declared critical points."""

    run: FlowCoro
    critical_points: tuple[str, ...] = field(default=())


CLOSED_CATALOG: dict[FlowName, FlowSpec] = {
    "checkout_full": FlowSpec(
        checkout_full.run,
        critical_points=("checkout_payment", "payment_failure_validation"),
    ),
    "checkout_card_declined": FlowSpec(
        checkout_card_declined.run, critical_points=("verify_decline_message",)
    ),
    "search_and_filter": FlowSpec(search_and_filter.run),
    "browse_discounted_products": FlowSpec(
        browse_discounted_products.run, critical_points=("pdp_discount_consistency",)
    ),
    "pdp_validation": FlowSpec(pdp_validation.run),
    "cart_review": FlowSpec(
        cart_review.run, critical_points=("cart_price_consistency",)
    ),
}
"""The closed catalog — adding an entry is a curated PR (invariant #2)."""

# Backwards-compatible name→coro registry consumed by the runner / orchestrator.
FLOW_REGISTRY: dict[str, FlowCoro] = {
    name: spec.run for name, spec in CLOSED_CATALOG.items()
}

COMPOSITIONS: dict[str, list[FlowName]] = {
    "full_journey": [
        "search_and_filter",
        "pdp_validation",
        "cart_review",
        "checkout_full",
    ],
}
"""Declared composition aliases. ``full_journey`` expands to this sequence."""


def expand_flows(flows: list[FlowSelection]) -> list[FlowName]:
    """Expand composition aliases and dedupe, preserving first-seen order.

    ``full_journey`` becomes its declared sequence; duplicates are dropped. An
    out-of-catalog value raises ``ValueError``. ``full_journey`` is never returned.
    """
    result: list[FlowName] = []
    for flow in flows:
        if flow in COMPOSITIONS:
            members: list[FlowName] = COMPOSITIONS[flow]
        elif flow in CLOSED_CATALOG:
            members = [cast(FlowName, flow)]
        else:
            raise ValueError(f"flow not in closed catalog: {flow}")
        for member in members:
            if member not in result:
                result.append(member)
    return result


def is_composition(flows: list[FlowSelection]) -> bool:
    """True if any requested flow is a composition alias (e.g. ``full_journey``)."""
    return any(flow in COMPOSITIONS for flow in flows)
