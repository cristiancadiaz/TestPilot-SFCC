from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.app import create_app

API_KEY = "test-key-123"
H = {"X-API-Key": API_KEY}


class BadTranslator:
    def translate(self, instruction: str):
        # Return a proposed_config that references an out-of-catalog flow
        return {
            "status": "ok",
            "proposed_config": {
                "schema_version": "v2",
                "environment_id": "staging",
                "flows": ["nonexistent_flow"],
                "mode": "gate",
                "profiles": ["mobile_co"],
                "products": [{"search_term": "x", "validate_variant": True}],
            },
            "explanation": "malicious",
            "clarification_question": None,
        }


def _client() -> TestClient:
    return TestClient(create_app(translator=BadTranslator(), serve_dashboard=False))


def test_out_of_catalog_is_instruction_rejected(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", API_KEY)
    client = _client()
    resp = client.post("/v1/translate", json={"instruction": "run whatever"}, headers=H)
    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "instruction_rejected"
