"""API-only Pydantic schemas for TestPilot SFCC — U4.

These models have **no** ``specs/`` JSON Schema (unlike the run/report/translate
contracts in ``src/models.py``). They are the request/response shapes for the
environment registry, live status, run history and error envelope, consumed by
the dashboard (MD0 ``src/dashboard/src/types/api.ts``) and CI/CD.

Invariant note: ``orders_created`` is published as ``0`` in ``RunStatus`` and
``RunListItem`` (MD0 expects it present and zero) — unlike the ``ExecutionReport``
contract, which excludes it.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models import EnvironmentId, FlowName, Mode, ProfileId, TrafficLight


class EnvironmentConfig(BaseModel):
    """Registry record for a target SFCC environment (DynamoDB table ``environments``).

    Credentials never live here — only the Secrets Manager *paths* do. The
    resolver (S6) fetches the actual credentials at run time.
    """

    model_config = ConfigDict(extra="forbid")

    environment_id: EnvironmentId
    store_url: str = Field(min_length=8)
    env_access_secret_path: str = Field(min_length=1)
    shopper_secret_path: str = Field(min_length=1)
    active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("store_url")
    @classmethod
    def _https_only(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("store_url must be an https URL")
        return value


class EnvironmentUpdate(BaseModel):
    """Mutable fields of an environment (PUT). ``environment_id`` cannot change."""

    model_config = ConfigDict(extra="forbid")

    store_url: str | None = None
    env_access_secret_path: str | None = None
    shopper_secret_path: str | None = None
    active: bool | None = None

    @field_validator("store_url")
    @classmethod
    def _https_only(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("https://"):
            raise ValueError("store_url must be an https URL")
        return value


class RunState(str, Enum):
    """Lifecycle state of a run / profile execution (live tracker, S7)."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProfileRunStatus(BaseModel):
    """Live status of a single profile×flow combination within a run."""

    model_config = ConfigDict(extra="forbid")

    profile_name: ProfileId
    flow_name: FlowName
    state: RunState = RunState.PENDING
    current_step: str | None = None
    steps_completed: int = Field(default=0, ge=0)


class RunStatus(BaseModel):
    """Live status payload served by ``GET /v1/runs/{id}/status`` (dashboard polling)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    environment_id: EnvironmentId
    state: RunState
    started_at: datetime
    traffic_light: TrafficLight | None = None
    profiles: list[ProfileRunStatus]
    orders_created: int = 0  # published as 0 (MD0 contract)


class RunListItem(BaseModel):
    """One row in the paginated run history."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    environment_id: EnvironmentId
    mode: Mode
    traffic_light: TrafficLight
    started_at: datetime
    finished_at: datetime
    duration_ms: int = Field(ge=0)
    orders_created: int = 0  # published as 0 (MD0 contract)


class RunListResponse(BaseModel):
    """Paginated response of ``GET /v1/runs``."""

    model_config = ConfigDict(extra="forbid")

    items: list[RunListItem]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    has_more: bool


class RunListQuery(BaseModel):
    """Validated query params for ``GET /v1/runs`` (BR-U4-16: default last 7 days)."""

    model_config = ConfigDict(extra="forbid")

    environment_id: EnvironmentId | None = None
    traffic_light: TrafficLight | None = None
    flow: FlowName | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ApiErrorPayload(BaseModel):
    """Uniform error envelope for every HTTP >= 400 (error-taxonomy §3).

    NEVER carries stack traces, server paths, secret values, or auth headers.
    """

    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    request_id: str
    details: dict[str, Any] | None = None
