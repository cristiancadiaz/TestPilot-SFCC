from __future__ import annotations

from typing import Protocol, TypedDict, cast


class TranslationResult(TypedDict):
    status: str  # 'ok' | 'ambiguous'
    proposed_config: dict[str, object] | None
    explanation: str | None
    clarification_question: str | None


class TranslatorProtocol(Protocol):
    """Protocol for a translator implementation (NL -> TranslateResponse-like)."""

    def translate(self, instruction: str) -> TranslationResult:
        ...


class InMemoryTranslatorFake:
    """A tiny deterministic fake translator for tests and local runs.

    Heuristics:
    - If instruction contains the word 'ambiguous' -> returns ambiguous
    - If instruction length > 2000 -> raises ValueError (validation elsewhere)
    - Otherwise returns a simple valid SyntheticUserConfig-like dict
    """

    def translate(self, instruction: str) -> TranslationResult:
        inst = (instruction or "").strip()
        if not inst:
            return {
                "status": "ambiguous",
                "proposed_config": None,
                "explanation": None,
                "clarification_question": "Por favor proporciona una instrucción válida.",
            }
        if "ambiguous" in inst.lower():
            return {
                "status": "ambiguous",
                "proposed_config": None,
                "explanation": None,
                "clarification_question": "¿Puedes especificar si quieres el recorrido completo o un módulo?",
            }
        # Return a minimal valid proposed_config
        proposed = {
            "schema_version": "v2",
            "environment_id": "staging",
            "flows": ["pdp_validation"],
            "mode": "gate",
            "profiles": ["mobile_co"],
            "products": [{"search_term": "producto de prueba", "validate_variant": True}],
        }
        return {
            "status": "ok",
            "proposed_config": cast(dict[str, object], proposed),
            "explanation": "Voy a validar la página de detalle de un producto en staging con perfil móvil Colombia.",
            "clarification_question": None,
        }
