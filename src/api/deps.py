"""FastAPI dependency providers — U4.

These read singletons wired onto ``app.state`` by ``create_app`` (avoids a circular
import between routers and the app factory).
"""

from __future__ import annotations

from fastapi import Request

from src.api.services.environment_registry import EnvironmentRegistry
from src.api.services.live_status_tracker import LiveStatusTracker
from src.api.services.run_orchestrator import RunOrchestrator
from src.api.stores import RunReportStore, ScreenshotStore


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
