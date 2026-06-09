"""Health router — U4. ``GET /health`` (no auth). 503 if a dependency probe fails."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    """Liveness/readiness probe. 200 when healthy, 503 when a dependency is down."""
    probe = getattr(request.app.state, "health_probe", None)
    healthy = True if probe is None else bool(probe())
    if healthy:
        return JSONResponse(content={"status": "ok"})
    return JSONResponse(status_code=503, content={"status": "unavailable"})
