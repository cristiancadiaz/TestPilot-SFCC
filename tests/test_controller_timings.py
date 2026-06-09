"""Tests for src/executor/controller_timings.py (U7).

SFRA controller URLs aggregate (count + p95); asset / non-controller URLs are
excluded; the p95 matches U2's ceiling-index method.
"""

from __future__ import annotations

from datetime import datetime

from src.baseline import calculate_p95
from src.executor.controller_timings import aggregate_controllers, extract_controller
from src.executor.network_capture import RequestRecord
from src.models import RunRecord


def _rec(url: str, duration_ms: int) -> RequestRecord:
    return RequestRecord(
        url=url,
        method="GET",
        status=200,
        resource_type="document",
        duration_ms=duration_ms,
        size=0,
    )


def test_extract_controller() -> None:
    assert extract_controller("https://x/Product-Show?pid=1") == "Product-Show"
    assert extract_controller("https://x/on/demand/Cart-AddProduct") == "Cart-AddProduct"
    assert extract_controller("https://x/css/app.css") is None
    assert extract_controller("https://x/images/hero.png") is None
    assert extract_controller("https://x/") is None


def test_aggregate_groups_and_excludes_assets() -> None:
    records = [
        _rec("https://x/Product-Show?pid=1", 100),
        _rec("https://x/Product-Show?pid=2", 200),
        _rec("https://x/Product-Show?pid=3", 300),
        _rec("https://x/Cart-AddProduct", 150),
        _rec("https://x/css/app.css", 10),
        _rec("https://x/images/hero.png", 5),
    ]
    result = aggregate_controllers(records)
    by_pattern = {c.pattern: c for c in result}
    assert set(by_pattern) == {"Product-Show", "Cart-AddProduct"}  # assets excluded
    assert by_pattern["Product-Show"].count == 3
    assert by_pattern["Cart-AddProduct"].count == 1


def test_p95_consistent_with_u2() -> None:
    durations = [100, 200, 300]
    records = [_rec(f"https://x/Product-Show?pid={d}", d) for d in durations]
    timing = aggregate_controllers(records)[0]
    runs = [
        RunRecord(
            run_id="r",
            environment_id="staging",
            profile_name="mobile_co",
            flow_name="pdp_validation",
            duration_ms=d,
            status="success",
            created_at=datetime(2026, 1, 1),
        )
        for d in durations
    ]
    assert timing.p95_ms == calculate_p95(runs)  # same ceiling-index method


def test_sorted_slowest_first() -> None:
    records = [
        _rec("https://x/Search-Show", 50),
        _rec("https://x/Checkout-Begin", 900),
        _rec("https://x/Cart-Show", 400),
    ]
    result = aggregate_controllers(records)
    assert [c.pattern for c in result] == ["Checkout-Begin", "Cart-Show", "Search-Show"]
