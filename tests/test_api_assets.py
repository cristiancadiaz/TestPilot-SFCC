"""Screenshots endpoint + static dashboard serving (U4 Phase C, S8)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.stores import InMemoryScreenshotStore

API_KEY = "test-key-123"
H = {"X-API-Key": API_KEY}
RUN_ID = "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", API_KEY)


def test_screenshot_redirects_to_url() -> None:
    key = f"runs/{RUN_ID}/mobile_co/checkout_full/final.png"
    store = InMemoryScreenshotStore({key: "https://evidence.example.com/x.png"})
    client = TestClient(
        create_app(screenshot_store=store, serve_dashboard=False)
    )
    resp = client.get(
        f"/v1/runs/{RUN_ID}/screenshots/mobile_co/checkout_full/final.png",
        headers=H,
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://evidence.example.com/x.png"


def test_screenshot_missing_is_404() -> None:
    client = TestClient(
        create_app(screenshot_store=InMemoryScreenshotStore(), serve_dashboard=False)
    )
    resp = client.get(
        f"/v1/runs/{RUN_ID}/screenshots/mobile_co/checkout_full/final.png",
        headers=H,
        follow_redirects=False,
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "screenshot_not_found"


def test_screenshot_requires_auth() -> None:
    client = TestClient(
        create_app(screenshot_store=InMemoryScreenshotStore(), serve_dashboard=False)
    )
    resp = client.get(
        f"/v1/runs/{RUN_ID}/screenshots/x.png", follow_redirects=False
    )
    assert resp.status_code == 401


def test_dashboard_served_at_root() -> None:
    # The MD0 dashboard was built (src/dashboard/dist exists), so it mounts at "/".
    client = TestClient(create_app(serve_dashboard=True))
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    # Security headers apply to the static response too.
    assert resp.headers["X-Frame-Options"] == "DENY"


def test_health_works_with_dashboard_mounted() -> None:
    client = TestClient(create_app(serve_dashboard=True))
    assert client.get("/health").status_code == 200
