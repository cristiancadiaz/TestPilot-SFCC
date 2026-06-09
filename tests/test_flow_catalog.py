"""Tests for the closed flow catalog (U5, invariant #2).

Covers ``expand_flows`` (composition expansion + dedupe + out-of-catalog
rejection), ``is_composition``, and the **static** zero-payment guarantee for the
journey flows: a journey flow may NEVER import a PAYMENT selector or declare a
payment critical point (only ``checkout_*`` flows touch payment — invariant #1/C3).
"""

from __future__ import annotations

import inspect

import pytest

from src.executor.flow_catalog import (
    CLOSED_CATALOG,
    COMPOSITIONS,
    expand_flows,
    is_composition,
)
from src.executor.flows import (
    browse_discounted_products,
    cart_review,
    pdp_validation,
    search_and_filter,
)

JOURNEY_FLOWS = {
    "search_and_filter": search_and_filter,
    "browse_discounted_products": browse_discounted_products,
    "pdp_validation": pdp_validation,
    "cart_review": cart_review,
}

FULL_JOURNEY_SEQUENCE = [
    "search_and_filter",
    "pdp_validation",
    "cart_review",
    "checkout_full",
]


# ---------------------------------------------------------------------------
# expand_flows
# ---------------------------------------------------------------------------


def test_full_journey_expands_to_declared_sequence() -> None:
    assert expand_flows(["full_journey"]) == FULL_JOURNEY_SEQUENCE
    assert COMPOSITIONS["full_journey"] == FULL_JOURNEY_SEQUENCE


def test_full_journey_never_returned_as_a_flow() -> None:
    # full_journey is a composition alias, never a flow file (D15).
    assert "full_journey" not in expand_flows(["full_journey"])
    assert "full_journey" not in CLOSED_CATALOG


def test_expand_dedupes_preserving_order() -> None:
    # full_journey already contains cart_review → no duplicate appended.
    assert expand_flows(["full_journey", "cart_review"]) == FULL_JOURNEY_SEQUENCE
    # Plain duplicates collapse, first-seen order preserved.
    assert expand_flows(["pdp_validation", "pdp_validation"]) == ["pdp_validation"]
    assert expand_flows(["cart_review", "search_and_filter", "cart_review"]) == [
        "cart_review",
        "search_and_filter",
    ]


def test_out_of_catalog_raises() -> None:
    with pytest.raises(ValueError, match="closed catalog"):
        expand_flows(["nonexistent_flow"])  # type: ignore[list-item]


def test_is_composition() -> None:
    assert is_composition(["full_journey"]) is True
    assert is_composition(["full_journey", "cart_review"]) is True
    assert is_composition(["cart_review"]) is False
    assert is_composition(["checkout_full", "pdp_validation"]) is False


def test_every_catalog_entry_has_a_run_coroutine() -> None:
    for name, spec in CLOSED_CATALOG.items():
        assert callable(spec.run), name


# ---------------------------------------------------------------------------
# Static zero-payment guarantee (invariant #1 / C3) — journey flows
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flow_name", sorted(JOURNEY_FLOWS))
def test_journey_flow_never_imports_payment_selectors(flow_name: str) -> None:
    """A journey flow's source must not reference any PAYMENT_* selector."""
    source = inspect.getsource(JOURNEY_FLOWS[flow_name])
    assert "PAYMENT_" not in source, (
        f"{flow_name} references a PAYMENT selector — journey flows never pay"
    )
    # No payment / place-order step names either.
    assert "place-order" not in source
    assert "place_order" not in source


@pytest.mark.parametrize("flow_name", sorted(JOURNEY_FLOWS))
def test_journey_flow_has_no_payment_critical_point(flow_name: str) -> None:
    spec = CLOSED_CATALOG[flow_name]  # type: ignore[index]
    assert all("payment" not in cp.lower() for cp in spec.critical_points)
