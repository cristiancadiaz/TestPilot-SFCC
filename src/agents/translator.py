from __future__ import annotations

from typing import Protocol, TypedDict, cast
import re
import base64
import unicodedata
from typing import Optional

from src.api.errors import InstructionRejectedError


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
    - If instruction matches common prompt-injection patterns -> raise InstructionRejectedError
    - Otherwise returns a simple valid SyntheticUserConfig-like dict
    """

    _INJECTION_PATTERNS = [
        r"ignore\s+the\s+rules",
        r"ignore\s+previous\s+instructions",
        r"jailbreak",
        r"bypass\s+safety",
        r"leak\s+.*(env|secret|password|credentials)",
        r"exfiltrat",
        r"place[-_ ]?order",
        r"pay(ment)?",
        r"send\s+the\s+secret",
        r"ignore\s+guidelines",
    ]

    def translate(self, instruction: str) -> TranslationResult:
        inst = (instruction or "").strip()
        if not inst:
            return {
                "status": "ambiguous",
                "proposed_config": None,
                "explanation": None,
                "clarification_question": "Por favor proporciona una instrucción válida.",
            }

        if len(inst) > 2000:
            # Let validation at the router surface this as a 422 validation_failed
            raise ValueError("instruction too long")

        lower = inst.lower()

        # Normalize forms to detect obfuscation:
        #  - zero-width and diacritics removed
        #  - alphanumeric-only collapsed (e.g., 'j a i l b r e a k' -> 'jailbreak')
        def remove_zero_width(s: str) -> str:
            return s.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")

        def strip_diacritics(s: str) -> str:
            return "".join(
                c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
            )

        cleaned = strip_diacritics(remove_zero_width(lower))
        alnum_only = re.sub(r"[^a-z0-9]", "", cleaned)

        # Try base64 decode if the instruction looks like a base64 blob and check decoded content
        decoded_candidate: Optional[str] = None
        try:
            # Use original-cased instruction (after removing zero-width/diacritics) for decoding
            possible = strip_diacritics(remove_zero_width(inst)).strip()
            # Accept only reasonably short base64 strings to avoid accidental decodes
            if 8 <= len(possible) <= 512 and re.fullmatch(r"[A-Za-z0-9+/=\n\r]+", possible):
                try:
                    dec = base64.b64decode(possible, validate=True)
                    decoded_candidate = dec.decode("utf-8", errors="ignore").lower()
                except Exception:
                    decoded_candidate = None
        except Exception:
            decoded_candidate = None

        # Simple heuristic checks for prompt-injection / malicious content against multiple normalizations
        for pat in self._INJECTION_PATTERNS:
            if re.search(pat, lower) or re.search(pat, cleaned) or re.search(pat, alnum_only):
                raise InstructionRejectedError("prompt injection detected")
            if decoded_candidate and re.search(pat, decoded_candidate):
                raise InstructionRejectedError("prompt injection detected")

        if "ambiguous" in lower:
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
