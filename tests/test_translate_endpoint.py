from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.agents.translator import InMemoryTranslatorFake

API_KEY = "test-key-123"
H = {"X-API-Key": API_KEY}


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", API_KEY)


def _client() -> TestClient:
    return TestClient(create_app(translator=InMemoryTranslatorFake(), serve_dashboard=False))


def test_translate_ok_returns_proposed_config() -> None:
    client = _client()
    resp = client.post("/v1/translate", json={"instruction": "valida la PDP"}, headers=H)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["proposed_config"] is not None
    assert "explanation" in body


def test_translate_ambiguous_returns_question() -> None:
    client = _client()
    resp = client.post("/v1/translate", json={"instruction": "esto es ambiguous por diseño"}, headers=H)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ambiguous"
    assert body["clarification_question"] is not None


def test_translate_requires_api_key() -> None:
    client = _client()
    resp = client.post("/v1/translate", json={"instruction": "valida la PDP"})
    assert resp.status_code == 401


def test_translate_instruction_too_long_is_422() -> None:
    client = _client()
    instr = "x" * 2001
    resp = client.post("/v1/translate", json={"instruction": instr}, headers=H)
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "validation_failed"
