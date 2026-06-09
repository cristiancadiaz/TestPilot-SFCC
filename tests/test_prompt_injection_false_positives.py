from __future__ import annotations

from typing import List

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app

API_KEY = "test-key-123"
H = {"X-API-Key": API_KEY}


def _client() -> TestClient:
    from src.agents.translator import InMemoryTranslatorFake

    return TestClient(create_app(translator=InMemoryTranslatorFake(), serve_dashboard=False))


@pytest.mark.parametrize(
    "instruction",
    [
        "Valida el PDP para el producto X en staging",
        "¿Cuánto debo pagar por este envío?",
        "Revisa el precio 😊",
        "Buscar 'camisa #42' y validar variantes",
        "Mostrar descuentos activos y disponibilidad por talla",
        "Realiza una búsqueda por categoría 'zapatos' y filtra por precio",
        "Genera un resumen de stocks para el SKU 123-ABC",
        "Validar comportamiento de paginación en PLP con 50 resultados",
        "Comprueba que la etiqueta 'nuevo' aparece en productos recientes",
        "Consulta si el selector CSS .product-title existe en PDP",
    ],
)
def test_benign_instructions_not_rejected(monkeypatch: "pytest.MonkeyPatch", instruction: str) -> None:
    monkeypatch.setenv("API_KEY", API_KEY)
    client = _client()
    resp = client.post("/v1/translate", json={"instruction": instruction}, headers=H)
    assert resp.status_code == 200, f"expected 200 for benign input: {instruction}"
    body = resp.json()
    assert not (body.get("error_code") == "instruction_rejected"), f"false positive on: {instruction}"
