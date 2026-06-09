"""FastAPI dependency providers — U4.

These read singletons wired onto ``app.state`` by ``create_app`` (avoids a circular
import between routers and the app factory).
"""

from __future__ import annotations

from fastapi import Request

from src.api.services.live_status_tracker import LiveStatusTracker
from src.api.services.run_orchestrator import RunOrchestrator


def get_orchestrator(request: Request) -> RunOrchestrator:
    """Return the request-scoped ``RunOrchestrator`` from app state."""
    orchestrator: RunOrchestrator = request.app.state.orchestrator
    return orchestrator


def get_tracker(request: Request) -> LiveStatusTracker:
    """Return the live status tracker from app state."""
    tracker: LiveStatusTracker = request.app.state.tracker
    return tracker
