"""Runs router — U4. Phase A: ``POST /v1/run`` (orchestrated run).

The response is serialized via U3's ``to_json_dict`` so it is exactly the
schema-valid ``ExecutionReport`` (snake_case, ISO datetimes, ``orders_created``
excluded). The ``X-Run-Id`` header carries the run id (D9).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.deps import get_orchestrator
from src.api.security import verify_api_key
from src.api.services.run_orchestrator import RunOrchestrator
from src.models import SyntheticUserConfig
from src.reporter import to_json_dict

router = APIRouter(prefix="/v1", tags=["runs"])


@router.post("/run", dependencies=[Depends(verify_api_key)])
async def create_run(
    config: SyntheticUserConfig,
    orchestrator: RunOrchestrator = Depends(get_orchestrator),
) -> JSONResponse:
    """Run *config* across its profiles×flows and return the ``ExecutionReport``."""
    report = await orchestrator.execute(config)
    return JSONResponse(
        content=to_json_dict(report),
        headers={"X-Run-Id": report.run_id},
    )
