"""Tests for src/executor/network_capture.py (U7, RNF-15 redaction is blocking).

No real browser. Covers the domain allowlist, header redaction, the absence of any
response body in the HAR, and credential-query stripping.
"""

from __future__ import annotations

import json

from src.executor.network_capture import (
    NetworkCapture,
    _strip_credentials,
)

STORE = "https://staging.example.com"


def _capture() -> NetworkCapture:
    return NetworkCapture(STORE)


# ---------------------------------------------------------------------------
# Domain allowlist
# ---------------------------------------------------------------------------


def test_allowlist_keeps_store_host_and_subdomains() -> None:
    cap = _capture()
    assert cap.host_allowed("https://staging.example.com/Product-Show")
    assert cap.host_allowed("https://cdn.staging.example.com/x.js")  # subdomain
    assert not cap.host_allowed("https://www.google-analytics.com/collect")
    assert not cap.host_allowed("https://connect.facebook.net/sdk.js")


def test_record_response_drops_third_party() -> None:
    cap = _capture()
    cap.record_response(
        url="https://staging.example.com/Search-Show",
        method="GET",
        status=200,
        resource_type="document",
        duration_ms=120,
    )
    cap.record_response(
        url="https://www.google-analytics.com/collect",
        method="POST",
        status=200,
        resource_type="xhr",
        duration_ms=30,
    )
    assert len(cap.records) == 1
    assert cap.records[0].url.endswith("/Search-Show")


# ---------------------------------------------------------------------------
# Redaction (RNF-15 — blocking)
# ---------------------------------------------------------------------------


def test_har_redacts_auth_headers_and_cookies() -> None:
    cap = _capture()
    cap.record_response(
        url="https://staging.example.com/Cart-Show",
        method="GET",
        status=200,
        resource_type="document",
        duration_ms=80,
        headers={
            "Authorization": "Bearer SUPER-SECRET-TOKEN",
            "Cookie": "sid=ABC123SESSION",
            "Accept": "text/html",
        },
    )
    blob = json.dumps(cap.to_har_dict())
    # Secret values and their header names must be gone.
    assert "SUPER-SECRET-TOKEN" not in blob
    assert "ABC123SESSION" not in blob
    assert "Authorization" not in blob
    assert "Cookie" not in blob
    # Non-sensitive headers survive.
    assert "Accept" in blob


def test_har_never_contains_bodies() -> None:
    cap = _capture()
    cap.record_response(
        url="https://staging.example.com/Product-Show",
        method="GET",
        status=200,
        resource_type="document",
        duration_ms=90,
    )
    har = cap.to_har_dict()
    entry = har["log"]["entries"][0]
    assert "postData" not in entry["request"]
    assert entry["response"]["bodySize"] == -1
    assert entry["response"]["content"] == {}


def test_credential_query_params_stripped() -> None:
    url = "https://staging.example.com/Account-Login?password=p%40ss&token=XYZ&pid=123"
    cleaned = _strip_credentials(url)
    assert "password" not in cleaned
    assert "p%40ss" not in cleaned and "p@ss" not in cleaned
    assert "token" not in cleaned and "XYZ" not in cleaned
    assert "pid=123" in cleaned  # non-credential param kept


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def test_build_summary_counts_total_and_failed() -> None:
    cap = _capture()
    for status in (200, 200, 404, 500):
        cap.record_response(
            url=f"https://staging.example.com/p/{status}",
            method="GET",
            status=status,
            resource_type="document",
            duration_ms=50,
        )
    cap.record_failure(
        url="https://staging.example.com/dead",
        method="GET",
        resource_type="xhr",
    )
    summary = cap.build_summary(controllers=[], web_vitals=None, har_url="k")
    assert summary.total_requests == 5
    assert summary.failed_requests == 3  # 404 + 500 + the hard failure


def test_reset_clears_records() -> None:
    cap = _capture()
    cap.record_response(
        url="https://staging.example.com/x",
        method="GET",
        status=200,
        resource_type="document",
        duration_ms=10,
    )
    cap.reset()
    assert cap.records == []
