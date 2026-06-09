"""EnvironmentRegistry (S5) — CRUD of ``EnvironmentConfig`` records.

Serves the dashboard P1 and feeds S6 (resolver). On create, both Secrets Manager
paths are probed (BR-U4-07) so a misconfigured environment fails fast at
registration rather than at run time. Update/deactivate invalidate the resolver
cache so changes propagate immediately.

Wave-1 note: backed by the in-memory ``EnvironmentStore`` (D-U4-1). The 60s read
cache (NFR-U4-P1) belongs to the DynamoDB adapter and is deferred with it.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.api.errors import (
    EnvironmentAlreadyExistsError,
    EnvironmentNotFoundError,
    InvalidSecretPathError,
    SecretNotFoundError,
)
from src.api.schemas import EnvironmentConfig, EnvironmentUpdate
from src.api.services.environment_resolver import EnvironmentResolver
from src.api.stores import EnvironmentStore, SecretsClient
from src.models import EnvironmentId


class EnvironmentRegistry:
    """CRUD over ``EnvironmentConfig`` with secret-path validation on create."""

    def __init__(
        self,
        store: EnvironmentStore,
        secrets: SecretsClient,
        resolver: EnvironmentResolver | None = None,
    ) -> None:
        self._store = store
        self._secrets = secrets
        self._resolver = resolver

    def create(self, config: EnvironmentConfig) -> EnvironmentConfig:
        """Register a new environment. 409 if it exists; 422 if a secret path is bad."""
        if self._store.get(config.environment_id) is not None:
            raise EnvironmentAlreadyExistsError(
                "environment already registered",
                details={"environment_id": config.environment_id},
            )
        # BR-U4-07: both secret paths must resolve at registration time.
        for path in (config.env_access_secret_path, config.shopper_secret_path):
            try:
                self._secrets.get_json(path)
            except SecretNotFoundError as exc:
                raise InvalidSecretPathError(
                    "secret path does not resolve",
                    details={"environment_id": config.environment_id},
                ) from exc
        now = datetime.now(timezone.utc)
        stored = config.model_copy(update={"created_at": now, "updated_at": now})
        self._store.put(stored)
        return stored

    def list(self, *, only_active: bool = False) -> list[EnvironmentConfig]:
        return self._store.list(only_active=only_active)

    def get(self, environment_id: EnvironmentId) -> EnvironmentConfig:
        config = self._store.get(environment_id)
        if config is None:
            raise EnvironmentNotFoundError(
                "environment is not registered",
                details={"environment_id": environment_id},
            )
        return config

    def update(
        self, environment_id: EnvironmentId, updates: EnvironmentUpdate
    ) -> EnvironmentConfig:
        existing = self.get(environment_id)  # 404 if missing
        patch = updates.model_dump(exclude_unset=True)
        merged = existing.model_copy(
            update={**patch, "updated_at": datetime.now(timezone.utc)}
        )
        self._store.put(merged)
        self._invalidate(environment_id)
        return merged

    def deactivate(self, environment_id: EnvironmentId) -> None:
        existing = self.get(environment_id)  # 404 if missing
        self._store.put(
            existing.model_copy(
                update={"active": False, "updated_at": datetime.now(timezone.utc)}
            )
        )
        self._invalidate(environment_id)

    def _invalidate(self, environment_id: EnvironmentId) -> None:
        if self._resolver is not None:
            self._resolver.invalidate(environment_id)
