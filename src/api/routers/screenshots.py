"""Screenshots router — U4 Phase C. Resolve evidence keys to fetchable URLs.

Evidence keys follow the ADR-003 naming
``runs/{run_id}/{profile}/{flow}/{step}-{state}.png``. The endpoint redirects to
the resolved URL (e.g. an S3 presigned URL) so the dashboard can use it directly
as an ``<img>`` source.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from src.api.deps import get_screenshot_store
from src.api.errors import ScreenshotNotFoundError
from src.api.security import verify_api_key
from src.api.stores import ScreenshotStore

router = APIRouter(prefix="/v1", tags=["screenshots"])


@router.get(
    "/runs/{run_id}/screenshots/{key:path}",
    dependencies=[Depends(verify_api_key)],
)
async def get_screenshot(
    run_id: UUID,
    key: str,
    store: ScreenshotStore = Depends(get_screenshot_store),
) -> RedirectResponse:
    """Redirect to the evidence URL for ``runs/{run_id}/{key}`` (404 if missing)."""
    full_key = f"runs/{run_id}/{key}"
    url = store.url_for(full_key)
    if url is None:
        raise ScreenshotNotFoundError(
            "screenshot not found", details={"key": full_key}
        )
    return RedirectResponse(url=url, status_code=307)
