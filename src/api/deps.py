"""FastAPI dependency providers — U4.

These read singletons wired onto ``app.state`` by ``create_app`` (avoids a circular
import between routers and the app factory).
"""

from __future__ import annotations

from fastapi import Request, Depends
from datetime import datetime, timezone

from src.api.services.environment_registry import EnvironmentRegistry
from src.api.services.live_status_tracker import LiveStatusTracker
from src.api.services.run_orchestrator import RunOrchestrator
from src.api.stores import RunReportStore, ScreenshotStore
from src.api.schemas import RunListQuery
from src.api.errors import RateLimitedError


def get_orchestrator(request: Request) -> RunOrchestrator:
    """Return the request-scoped ``RunOrchestrator`` from app state."""
    orchestrator: RunOrchestrator = request.app.state.orchestrator
    return orchestrator


def get_tracker(request: Request) -> LiveStatusTracker:
    """Return the live status tracker from app state."""
    tracker: LiveStatusTracker = request.app.state.tracker
    return tracker


def get_registry(request: Request) -> EnvironmentRegistry:
    """Return the environment registry from app state."""
    registry: EnvironmentRegistry = request.app.state.registry
    return registry


def get_report_store(request: Request) -> RunReportStore:
    """Return the run report store from app state."""
    report_store: RunReportStore = request.app.state.report_store
    return report_store


def get_screenshot_store(request: Request) -> ScreenshotStore:
    """Return the screenshot (evidence) store from app state."""
    screenshot_store: ScreenshotStore = request.app.state.screenshot_store
    return screenshot_store


# ---------------------------------------------------------------------------
# Operational guards / policies
# ---------------------------------------------------------------------------


def enforce_daily_cap(request: Request, report_store: RunReportStore = Depends(get_report_store)) -> None:
    """Count today's runs (gate + exploratory). Raise 429 when >= 10.

    Implemented as an in-app guard (D-U8-5). Full enforcement may be delegated
    to infrastructure, but the in-app guard prevents accidental overuse.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    query = RunListQuery(from_date=today_start, page=1, page_size=1)
    # Prefer the app-level report_store; fall back to the orchestrator's internal
    # reports when tests inject an orchestrator with its own store (see tests/_build).
    store = report_store or getattr(request.app.state, "report_store", None)
    if store is None:
        orchestrator = getattr(request.app.state, "orchestrator", None)
        store = getattr(orchestrator, "_reports", None)
    if store is None:
        return
    _, total = store.query(query)
    # If an orchestrator with its own report store is present (tests), prefer its count
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is not None and hasattr(orchestrator, "_reports"):
        try:
            _, o_total = orchestrator._reports.query(query)
            total = max(total, o_total)
        except Exception:
            pass
    if total >= 10:
        raise RateLimitedError("daily run cap exceeded")
