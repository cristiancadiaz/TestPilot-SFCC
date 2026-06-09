from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from src.api.security import verify_api_key
from src.api.errors import TestPilotApiError, ValidationFailedError, InstructionRejectedError
from src.models import TranslateRequest, TranslateResponse, SyntheticUserConfig
from src.executor.flow_catalog import expand_flows

router = APIRouter(prefix="/v1", tags=["translate"])


@router.post("/translate", dependencies=[Depends(verify_api_key)])
async def translate_endpoint(request_body: TranslateRequest, request: Request) -> JSONResponse:
    """Translate an NL instruction to a validated SyntheticUserConfig + explanation.

    The translator is injected onto app.state.translator by the app factory (create_app).
    The endpoint never launches the executor — it only returns a preview.
    """
    translator = getattr(request.app.state, "translator", None)
    if translator is None:
        raise TestPilotApiError("translator_not_configured", details={"hint": "create_app must be called with a translator dependency"})

    # Instruction length validated by TranslateRequest model already.
    result = translator.translate(request_body.instruction)

    status = result.get("status")
    if status == "ok":
        proposed = result.get("proposed_config")
        if proposed is None:
            raise ValidationFailedError("translator returned ok without proposed_config")
        # Expand compositions via the closed catalog BEFORE responding (P3).
        try:
            flows = proposed.get("flows", [])
            expanded = expand_flows(flows)
            proposed["flows"] = expanded
            # Validate against the SyntheticUserConfig model (mirrors specs v2).
            SyntheticUserConfig.model_validate(proposed)
        except ValueError as exc:
            # expand_flows raises ValueError on out-of-catalog — treat as instruction rejection
            raise InstructionRejectedError(str(exc), details={"error": str(exc)})
        except Exception as exc:  # other validation failures -> 422 validation_failed
            raise ValidationFailedError("proposed_config invalid", details={"error": str(exc)})

    # Build and return the TranslateResponse model (will validate fields)
    try:
        resp = TranslateResponse(**result)
    except Exception as exc:
        # Translator returned something malformed — surface as validation failed
        raise ValidationFailedError("translator_response_invalid", details={"error": str(exc)})

    return JSONResponse(status_code=200, content=resp.model_dump())
