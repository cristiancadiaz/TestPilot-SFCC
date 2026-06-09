"""EnvironmentResolver (S6) — resolve ``environment_id`` -> ``ResolvedEnvironment``.

Looks up the registry, fetches both credential secrets, and assembles the flat
``ResolvedEnvironment`` the executor consumes (ADR-001). Results are cached for
``cache_ttl_seconds`` (default 300) so manual secret rotation propagates within
5 minutes without hammering Secrets Manager.

Credentials never leave this layer except inside ``ResolvedEnvironment`` (which is
never serialized to a client).
"""

from __future__ import annotations

import time

from pydantic import ValidationError

from src.api.errors import (
    EnvironmentInactiveError,
    EnvironmentNotFoundError,
    InvalidSecretPathError,
)
from src.api.stores import EnvironmentStore, SecretsClient
from src.models import Credentials, EnvironmentId, ResolvedEnvironment


class EnvironmentResolver:
    """Resolve a registered environment id into credentials + URL, with a TTL cache."""

    def __init__(
        self,
        registry: EnvironmentStore,
        secrets: SecretsClient,
        *,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self._registry = registry
        self._secrets = secrets
        self._ttl = cache_ttl_seconds
        self._cache: dict[EnvironmentId, tuple[float, ResolvedEnvironment]] = {}

    def invalidate(self, environment_id: EnvironmentId) -> None:
        """Drop the cached resolution (called by the registry on update/delete)."""
        self._cache.pop(environment_id, None)

    def resolve(self, environment_id: EnvironmentId) -> ResolvedEnvironment:
        """Resolve *environment_id* to a ``ResolvedEnvironment``.

        Raises:
            EnvironmentNotFoundError: not registered (404).
            EnvironmentInactiveError: registered but ``active=False`` (409).
            SecretNotFoundError: a credential secret could not be fetched (502).
            InvalidSecretPathError: a secret exists but its JSON is malformed (422).
        """
        cached = self._cache.get(environment_id)
        if cached is not None and cached[0] > time.monotonic():
            return cached[1]

        config = self._registry.get(environment_id)
        if config is None:
            raise EnvironmentNotFoundError(
                "environment is not registered",
                details={"environment_id": environment_id},
            )
        if not config.active:
            raise EnvironmentInactiveError(
                "environment is inactive",
                details={"environment_id": environment_id},
            )

        # SecretNotFoundError (502) propagates from the secrets client.
        env_access_raw = self._secrets.get_json(config.env_access_secret_path)
        shopper_raw = self._secrets.get_json(config.shopper_secret_path)
        try:
            env_access = Credentials(**env_access_raw)
            shopper = Credentials(**shopper_raw)
        except ValidationError as exc:
            raise InvalidSecretPathError(
                "secret JSON does not match the expected shape",
                details={"environment_id": environment_id},
            ) from exc

        resolved = ResolvedEnvironment(
            environment_id=config.environment_id,
            store_url=config.store_url,
            env_access=env_access,
            shopper=shopper,
        )
        self._cache[environment_id] = (time.monotonic() + self._ttl, resolved)
        return resolved
