"""FastAPI application factory for TestPilot SFCC — U4.

Wires middlewares, the single structured exception handler (error-taxonomy §3),
and the routers. ``create_app`` accepts an injected orchestrator (tests pass one
wired to in-memory fakes); the default builds an in-memory orchestrator so the app
imports and runs without AWS credentials (decision D-U4-1).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.errors import TestPilotApiError
from src.api.middleware import RequestLoggingMiddleware, SecurityHeadersMiddleware
from src.api.routers import environments, health, runs, screenshots, translate
from src.api.schemas import ApiErrorPayload
from src.api.services.environment_registry import EnvironmentRegistry
from src.api.services.environment_resolver import EnvironmentResolver
from src.api.services.live_status_tracker import LiveStatusTracker
from src.api.services.run_orchestrator import RunOrchestrator
from src.api.stores import (
    InMemoryEnvironmentStore,
    InMemoryRunReportStore,
    InMemoryScreenshotStore,
    InMemorySecretsClient,
    RunReportStore,
    ScreenshotStore,
)
from src.baseline import BaselineManager, InMemoryBaselineStore

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "dist"

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


class _DefaultBundle:
    """In-memory collaborators sharing one set of stores (no AWS — D-U4-1)."""

    def __init__(self) -> None:
        env_store = InMemoryEnvironmentStore()
        secrets = InMemorySecretsClient()
        resolver = EnvironmentResolver(env_store, secrets)
        baseline = BaselineManager(InMemoryBaselineStore())
        self.report_store: RunReportStore = InMemoryRunReportStore()
        self.screenshot_store: ScreenshotStore = InMemoryScreenshotStore()
        self.tracker = LiveStatusTracker()
        self.orchestrator = RunOrchestrator(
            resolver, baseline, self.report_store, self.tracker
        )
        self.registry = EnvironmentRegistry(env_store, secrets, resolver)


def create_app(
    *,
    orchestrator: RunOrchestrator | None = None,
    tracker: LiveStatusTracker | None = None,
    registry: EnvironmentRegistry | None = None,
    report_store: RunReportStore | None = None,
    screenshot_store: ScreenshotStore | None = None,
    translator: object | None = None,
    serve_dashboard: bool = True,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Tests inject collaborators wired to in-memory fakes; with none provided, a
    default in-memory bundle is built so the app imports and runs without AWS.
    """
    app = FastAPI(title="TestPilot SFCC API", version="2.0.0")

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    app.add_exception_handler(TestPilotApiError, _api_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(Exception, _unhandled_handler)

    # /v1/* and /health are registered FIRST so they take priority over the
    # static SPA mount, which is added last and captures everything else.
    app.include_router(health.router)
    app.include_router(runs.router)
    app.include_router(environments.router)
    app.include_router(screenshots.router)
    # Translate router (U8)
    app.include_router(translate.router)

    bundle = _DefaultBundle()
    app.state.orchestrator = orchestrator or bundle.orchestrator
    app.state.tracker = tracker or bundle.tracker
    app.state.registry = registry or bundle.registry
    app.state.report_store = report_store or bundle.report_store
    app.state.screenshot_store = screenshot_store or bundle.screenshot_store
    # Translator dependency (injected by tests or the caller). May be None in default bundles.
    app.state.translator = translator
    app.state.health_probe = lambda: True

    # S8: serve the built dashboard if present; omit gracefully otherwise (BR-U4-22).
    if serve_dashboard and _DASHBOARD_DIR.exists():
        app.mount(
            "/", StaticFiles(directory=str(_DASHBOARD_DIR), html=True), name="dashboard"
        )
    return app


# Module-level app for `uvicorn src.api.app:app` (in-memory; seed environments at runtime).
app = create_app()
