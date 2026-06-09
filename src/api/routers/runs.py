"""Runs router — U4.

- Phase A: ``POST /v1/run`` (orchestrated run).
- Phase B: ``GET /v1/runs`` (list+filters), ``/latest`` (deploy decision, gate-only),
  ``/{id}`` (full report), ``/{id}/status`` (live polling state).

Report responses are serialized via U3's ``to_json_dict`` so they are exactly the
schema-valid ``ExecutionReport`` (snake_case, ISO datetimes, ``orders_created``
excluded).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from src.api.deps import (
    get_orchestrator,
    get_report_store,
    get_tracker,
)
from src.api.errors import NoRunsYetError, RunNotFoundError
from src.api.schemas import (
    RunListItem,
    RunListQuery,
    RunListResponse,
    RunStatus,
)
from src.api.security import verify_api_key
from src.api.services.live_status_tracker import LiveStatusTracker
from src.api.services.run_orchestrator import RunOrchestrator
from src.api.stores import RunReportStore
from src.models import EnvironmentId, FlowName, SyntheticUserConfig, TrafficLight
from src.reporter import to_json_dict

router = APIRouter(prefix="/v1", tags=["runs"])

_LATEST_TTL_SECONDS = 14_400  # 4 hours (deploy-gate freshness)


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


@router.get("/runs", dependencies=[Depends(verify_api_key)])
async def list_runs(
    environment_id: EnvironmentId | None = None,
    traffic_light: TrafficLight | None = None,
    flow: FlowName | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    report_store: RunReportStore = Depends(get_report_store),
) -> RunListResponse:
    """Paginated run history with filters (BR-U4-16: default last 7 days)."""
    if from_date is None and to_date is None:
        from_date = datetime.now(timezone.utc) - timedelta(days=7)
    query = RunListQuery(
        environment_id=environment_id,
        traffic_light=traffic_light,
        flow=flow,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )
    reports, total = report_store.query(query)
    items = [
        RunListItem(
            run_id=r.run_id,
            environment_id=r.environment_id,
            mode=r.mode,
            traffic_light=r.traffic_light,
            started_at=r.started_at,
            finished_at=r.finished_at,
            duration_ms=r.duration_ms,
        )
        for r in reports
    ]
    return RunListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


@router.get("/runs/latest", dependencies=[Depends(verify_api_key)])
async def latest_run(
    report_store: RunReportStore = Depends(get_report_store),
) -> JSONResponse:
    """Latest **gate** run + freshness meta for the deploy decision (gate-only)."""
    report = report_store.latest(mode="gate")
    if report is None:
        raise NoRunsYetError("no gate runs recorded yet")
    age_seconds = max(
        0, int((datetime.now(timezone.utc) - report.finished_at).total_seconds())
    )
    return JSONResponse(
        content={
            "report": to_json_dict(report),
            "age_seconds": age_seconds,
            "ttl_ok": age_seconds < _LATEST_TTL_SECONDS,
        }
    )


@router.get("/runs/{run_id}/status", dependencies=[Depends(verify_api_key)])
async def run_status(
    run_id: UUID,
    tracker: LiveStatusTracker = Depends(get_tracker),
) -> RunStatus:
    """Live status of an in-flight (or recently finished) run (404 if unknown)."""
    status = tracker.get(str(run_id))
    if status is None:
        raise RunNotFoundError(
            "run status not found", details={"run_id": str(run_id)}
        )
    return status


@router.get("/runs/{run_id}", dependencies=[Depends(verify_api_key)])
async def get_run(
    run_id: UUID,
    report_store: RunReportStore = Depends(get_report_store),
) -> JSONResponse:
    """Full ``ExecutionReport`` for a run (404 if unknown; 422 if not a UUID)."""
    report = report_store.get(str(run_id))
    if report is None:
        raise RunNotFoundError("run not found", details={"run_id": str(run_id)})
    return JSONResponse(content=to_json_dict(report))
