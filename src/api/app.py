"""FastAPI application factory for TestPilot SFCC — U4.

Wires middlewares, the single structured exception handler (error-taxonomy §3),
and the routers. ``create_app`` accepts an injected orchestrator (tests pass one
wired to in-memory fakes); the default builds an in-memory orchestrator so the app
imports and runs without AWS credentials (decision D-U4-1).
"""

from __future__ import annotations

import logging
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.errors import TestPilotApiError
from src.api.middleware import RequestLoggingMiddleware, SecurityHeadersMiddleware
from src.api.routers import health, runs
from src.api.schemas import ApiErrorPayload
from src.api.services.environment_resolver import EnvironmentResolver
from src.api.services.live_status_tracker import LiveStatusTracker
from src.api.services.run_orchestrator import RunOrchestrator
from src.api.stores import (
    InMemoryEnvironmentStore,
    InMemoryRunReportStore,
    InMemorySecretsClient,
)
from src.baseline import BaselineManager, InMemoryBaselineStore

logger = logging.getLogger("testpilot.api")


def _request_id(request: Request) -> str:
    return cast(str, getattr(request.state, "request_id", "unknown"))


async def _api_error_handler(request: Request, exc: Exception) -> JSONResponse:
    err = cast(TestPilotApiError, exc)
    payload = ApiErrorPayload(
        error_code=err.error_code,
        message=err.message,
        request_id=_request_id(request),
        details=err.details,
    )
    return JSONResponse(status_code=err.status_code, content=payload.model_dump())


async def _validation_handler(request: Request, exc: Exception) -> JSONResponse:
    err = cast(RequestValidationError, exc)
    details = {
        "errors": [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")}
            for e in err.errors()
        ]
    }
    payload = ApiErrorPayload(
        error_code="validation_failed",
        message="request failed validation",
        request_id=_request_id(request),
        details=details,
    )
    return JSONResponse(status_code=422, content=payload.model_dump())


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log server-side (no stack trace ever reaches the client — taxonomy §3).
    logger.error("unhandled exception: %s", type(exc).__name__)
    payload = ApiErrorPayload(
        error_code="internal_error",
        message="internal server error",
        request_id=_request_id(request),
    )
    return JSONResponse(status_code=500, content=payload.model_dump())


def _default_orchestrator() -> tuple[RunOrchestrator, LiveStatusTracker]:
    """Build an in-memory orchestrator (no AWS). Environments are seeded at runtime."""
    env_store = InMemoryEnvironmentStore()
    secrets = InMemorySecretsClient()
    resolver = EnvironmentResolver(env_store, secrets)
    baseline = BaselineManager(InMemoryBaselineStore())
    reports = InMemoryRunReportStore()
    tracker = LiveStatusTracker()
    orchestrator = RunOrchestrator(resolver, baseline, reports, tracker)
    return orchestrator, tracker


def create_app(
    *,
    orchestrator: RunOrchestrator | None = None,
    tracker: LiveStatusTracker | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="TestPilot SFCC API", version="2.0.0")

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    app.add_exception_handler(TestPilotApiError, _api_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(Exception, _unhandled_handler)

    app.include_router(health.router)
    app.include_router(runs.router)

    if orchestrator is None:
        orchestrator, default_tracker = _default_orchestrator()
        tracker = tracker or default_tracker
    app.state.orchestrator = orchestrator
    app.state.tracker = tracker or LiveStatusTracker()
    app.state.health_probe = lambda: True
    return app


# Module-level app for `uvicorn src.api.app:app` (in-memory; seed environments at runtime).
app = create_app()
