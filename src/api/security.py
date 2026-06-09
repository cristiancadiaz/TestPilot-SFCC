"""Authentication for TestPilot SFCC API — U4.

Every ``/v1/*`` endpoint depends on ``verify_api_key``. The expected key comes
from the ``API_KEY`` environment variable (resolved from Secrets Manager in
production). Fail-closed: a missing/empty ``API_KEY`` rejects every request
(D11 — auth fail-loud). The key value is never logged.
"""

from __future__ import annotations

import os

from fastapi import Header

from src.api.errors import UnauthorizedError

_API_KEY_ENV = "API_KEY"


def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """FastAPI dependency: reject the request unless ``X-API-Key`` matches ``API_KEY``.

    Raises:
        UnauthorizedError: header absent, or value does not match (401).
    """
    expected = os.environ.get(_API_KEY_ENV)
    if not expected or x_api_key != expected:
        raise UnauthorizedError("Missing or invalid X-API-Key")
