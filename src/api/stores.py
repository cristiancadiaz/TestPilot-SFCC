"""Storage abstractions for the API layer — U4 (decision D-U4-1).

Narrow Protocols with in-memory fakes for the wave-1 milestone — hermetic tests
and local end-to-end runs with NO AWS credentials (same pattern as U2's
``BaselineStore`` + ``InMemoryBaselineStore``). boto3-backed adapters (DynamoDB /
Secrets Manager / S3) are thin shims behind these Protocols, wired in the infra
milestone.

``RunReportStore`` is a U4-specific need: U2's ``BaselineStore`` holds only
flattened ``RunRecord``s, not the full ``ExecutionReport`` that ``GET /v1/runs/{id}``
must return.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Protocol, runtime_checkable

from src.api.errors import SecretNotFoundError
from src.api.schemas import EnvironmentConfig, RunListQuery
from src.models import EnvironmentId, ExecutionReport, Mode


# ---------------------------------------------------------------------------
# Environment registry store
# ---------------------------------------------------------------------------


@runtime_checkable
class EnvironmentStore(Protocol):
    """Persistence for ``EnvironmentConfig`` records."""

    def get(self, environment_id: EnvironmentId) -> EnvironmentConfig | None: ...

    def list(self, *, only_active: bool = False) -> list[EnvironmentConfig]: ...

    def put(self, config: EnvironmentConfig) -> None: ...


class InMemoryEnvironmentStore:
    """In-memory ``EnvironmentStore`` for tests and local runs."""

    def __init__(self) -> None:
        self._data: dict[str, EnvironmentConfig] = {}

    def get(self, environment_id: EnvironmentId) -> EnvironmentConfig | None:
        return self._data.get(environment_id)

    def list(self, *, only_active: bool = False) -> list[EnvironmentConfig]:
        configs = list(self._data.values())
        if only_active:
            configs = [c for c in configs if c.active]
        return configs

    def put(self, config: EnvironmentConfig) -> None:
        self._data[config.environment_id] = config


# ---------------------------------------------------------------------------
# Secrets client
# ---------------------------------------------------------------------------


@runtime_checkable
class SecretsClient(Protocol):
    """Fetch a JSON secret by path. Raises ``SecretNotFoundError`` if absent."""

    def get_json(self, path: str) -> dict[str, Any]: ...


class InMemorySecretsClient:
    """In-memory ``SecretsClient`` seeded with ``{path: {...}}`` mappings."""

    def __init__(self, secrets: dict[str, dict[str, Any]] | None = None) -> None:
        self._secrets: dict[str, dict[str, Any]] = dict(secrets or {})

    def set(self, path: str, value: dict[str, Any]) -> None:
        self._secrets[path] = value

    def get_json(self, path: str) -> dict[str, Any]:
        if path not in self._secrets:
            raise SecretNotFoundError("secret not found at the configured path")
        return self._secrets[path]


# ---------------------------------------------------------------------------
# Run report store (full ExecutionReport persistence)
# ---------------------------------------------------------------------------


@runtime_checkable
class RunReportStore(Protocol):
    """Persistence for full ``ExecutionReport`` objects, keyed by ``run_id``."""

    def save(self, report: ExecutionReport) -> None: ...

    def get(self, run_id: str) -> ExecutionReport | None: ...

    def latest(self, *, mode: Mode | None = None) -> ExecutionReport | None: ...

    def query(self, query: RunListQuery) -> tuple[list[ExecutionReport], int]: ...


class InMemoryRunReportStore:
    """In-memory ``RunReportStore``; preserves insertion order (newest last)."""

    def __init__(self) -> None:
        self._data: "OrderedDict[str, ExecutionReport]" = OrderedDict()

    def save(self, report: ExecutionReport) -> None:
        self._data[report.run_id] = report

    def get(self, run_id: str) -> ExecutionReport | None:
        return self._data.get(run_id)

    def latest(self, *, mode: Mode | None = None) -> ExecutionReport | None:
        reports = list(self._data.values())
        if mode is not None:
            reports = [r for r in reports if r.mode == mode]
        return reports[-1] if reports else None

    def query(self, query: RunListQuery) -> tuple[list[ExecutionReport], int]:
        reports = sorted(
            self._data.values(), key=lambda r: r.started_at, reverse=True
        )
        if query.environment_id is not None:
            reports = [r for r in reports if r.environment_id == query.environment_id]
        if query.traffic_light is not None:
            reports = [r for r in reports if r.traffic_light == query.traffic_light]
        if query.flow is not None:
            reports = [
                r
                for r in reports
                if any(
                    pr.flow_result.flow_name == query.flow
                    for pr in r.profile_results
                )
            ]
        if query.from_date is not None:
            reports = [r for r in reports if r.started_at >= query.from_date]
        if query.to_date is not None:
            reports = [r for r in reports if r.started_at <= query.to_date]
        total = len(reports)
        start = (query.page - 1) * query.page_size
        page_items = reports[start : start + query.page_size]
        return page_items, total


# ---------------------------------------------------------------------------
# Screenshot store (evidence URLs) — used in Phase C
# ---------------------------------------------------------------------------


@runtime_checkable
class ScreenshotStore(Protocol):
    """Resolve an evidence S3 key to a fetchable URL. ``None`` if missing."""

    def url_for(self, key: str) -> str | None: ...


class InMemoryScreenshotStore:
    """In-memory ``ScreenshotStore`` seeded with ``{key: url}`` mappings."""

    def __init__(self, urls: dict[str, str] | None = None) -> None:
        self._urls: dict[str, str] = dict(urls or {})

    def set(self, key: str, url: str) -> None:
        self._urls[key] = url

    def url_for(self, key: str) -> str | None:
        return self._urls.get(key)
