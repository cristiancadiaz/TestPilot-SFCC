"""Environments router (S5) — U4 Phase B. CRUD of registered SFCC environments."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from src.api.deps import get_registry
from src.api.schemas import EnvironmentConfig, EnvironmentUpdate
from src.api.security import verify_api_key
from src.api.services.environment_registry import EnvironmentRegistry
from src.models import EnvironmentId

router = APIRouter(
    prefix="/v1/environments",
    tags=["environments"],
    dependencies=[Depends(verify_api_key)],
)


@router.post("", status_code=201)
async def create_environment(
    config: EnvironmentConfig,
    registry: EnvironmentRegistry = Depends(get_registry),
) -> EnvironmentConfig:
    """Register a new environment (409 if it exists, 422 if a secret path is bad)."""
    return registry.create(config)


@router.get("")
async def list_environments(
    only_active: bool = False,
    registry: EnvironmentRegistry = Depends(get_registry),
) -> list[EnvironmentConfig]:
    """List registered environments (optionally only active ones)."""
    return registry.list(only_active=only_active)


@router.get("/{environment_id}")
async def get_environment(
    environment_id: EnvironmentId,
    registry: EnvironmentRegistry = Depends(get_registry),
) -> EnvironmentConfig:
    """Fetch one environment (404 if not registered)."""
    return registry.get(environment_id)


@router.put("/{environment_id}")
async def update_environment(
    environment_id: EnvironmentId,
    updates: EnvironmentUpdate,
    registry: EnvironmentRegistry = Depends(get_registry),
) -> EnvironmentConfig:
    """Update mutable fields (404 if not registered). ``environment_id`` is immutable."""
    return registry.update(environment_id, updates)


@router.delete("/{environment_id}", status_code=204)
async def deactivate_environment(
    environment_id: EnvironmentId,
    registry: EnvironmentRegistry = Depends(get_registry),
) -> Response:
    """Soft-delete (deactivate) an environment (404 if not registered)."""
    registry.deactivate(environment_id)
    return Response(status_code=204)
