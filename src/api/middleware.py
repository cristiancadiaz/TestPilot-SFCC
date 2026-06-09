"""ASGI middlewares for TestPilot SFCC API — U4.

- ``RequestLoggingMiddleware``: assigns a ``request_id`` (UUID4), exposes it on
  ``request.state`` (read by the exception handler) and as the ``X-Request-Id``
  response header, and emits a structured access log with NO secrets.
- ``SecurityHeadersMiddleware``: sets defensive headers + CSP on every response
  (Security baseline; closes MD0 Gate 6 CSP criterion).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("testpilot.api.access")

_Call = Callable[[Request], Awaitable[Response]]

# Content-Security-Policy for the dashboard SPA (served same-origin).
_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: blob:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Correlate every request with a UUID4 and log it without leaking secrets."""

    async def dispatch(self, request: Request, call_next: _Call) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)
        response.headers["X-Request-Id"] = request_id
        # Path only — never query strings or headers (may carry secrets).
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply defensive security headers + CSP to every response."""

    async def dispatch(self, request: Request, call_next: _Call) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = _CSP
        return response
