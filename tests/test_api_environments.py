"""Tests for the environments registry router (U4 Phase B, S5)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.services.environment_registry import EnvironmentRegistry
from src.api.services.environment_resolver import EnvironmentResolver
from src.api.stores import InMemoryEnvironmentStore, InMemorySecretsClient

API_KEY = "test-key-123"
H = {"X-API-Key": API_KEY}


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", API_KEY)


def _client(*, seed_secrets: bool = True) -> TestClient:
    env_store = InMemoryEnvironmentStore()
    secrets = InMemorySecretsClient()
    if seed_secrets:
        secrets.set("sm/env", {"username": "infra", "password": "p"})
        secrets.set("sm/shopper", {"username": "s@testpilot.internal", "password": "p"})
    resolver = EnvironmentResolver(env_store, secrets)
    registry = EnvironmentRegistry(env_store, secrets, resolver)
    return TestClient(create_app(registry=registry))


def _env_body(environment_id: str = "staging") -> dict[str, Any]:
    return {
        "environment_id": environment_id,
        "store_url": "https://staging.example.com",
        "env_access_secret_path": "sm/env",
        "shopper_secret_path": "sm/shopper",
        "active": True,
    }


def test_create_then_get() -> None:
    client = _client()
    resp = client.post("/v1/environments", json=_env_body(), headers=H)
    assert resp.status_code == 201
    assert resp.json()["environment_id"] == "staging"
    got = client.get("/v1/environments/staging", headers=H)
    assert got.status_code == 200
    assert got.json()["created_at"] is not None


def test_create_duplicate_is_409() -> None:
    client = _client()
    client.post("/v1/environments", json=_env_body(), headers=H)
    resp = client.post("/v1/environments", json=_env_body(), headers=H)
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "environment_already_exists"


def test_create_with_missing_secret_is_422() -> None:
    client = _client(seed_secrets=False)
    resp = client.post("/v1/environments", json=_env_body(), headers=H)
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "invalid_secret_path"


def test_get_unknown_is_404() -> None:
    client = _client()
    resp = client.get("/v1/environments/development", headers=H)
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "environment_not_found"


def test_invalid_environment_id_is_422() -> None:
    client = _client()
    resp = client.get("/v1/environments/produccion", headers=H)
    assert resp.status_code == 422  # not in the Literal enum


def test_list_and_only_active() -> None:
    client = _client()
    client.post("/v1/environments", json=_env_body("staging"), headers=H)
    client.post("/v1/environments", json=_env_body("sandbox"), headers=H)
    all_envs = client.get("/v1/environments", headers=H).json()
    assert len(all_envs) == 2
    # Deactivate one, then filter.
    client.delete("/v1/environments/sandbox", headers=H)
    active = client.get("/v1/environments?only_active=true", headers=H).json()
    assert {e["environment_id"] for e in active} == {"staging"}


def test_update_changes_fields() -> None:
    client = _client()
    client.post("/v1/environments", json=_env_body(), headers=H)
    resp = client.put(
        "/v1/environments/staging",
        json={"store_url": "https://new.example.com"},
        headers=H,
    )
    assert resp.status_code == 200
    assert resp.json()["store_url"] == "https://new.example.com"


def test_update_unknown_is_404() -> None:
    client = _client()
    resp = client.put(
        "/v1/environments/staging", json={"active": False}, headers=H
    )
    assert resp.status_code == 404


def test_delete_soft_deletes() -> None:
    client = _client()
    client.post("/v1/environments", json=_env_body(), headers=H)
    resp = client.delete("/v1/environments/staging", headers=H)
    assert resp.status_code == 204
    assert client.get("/v1/environments/staging", headers=H).json()["active"] is False


def test_requires_auth() -> None:
    client = _client()
    assert client.get("/v1/environments").status_code == 401
