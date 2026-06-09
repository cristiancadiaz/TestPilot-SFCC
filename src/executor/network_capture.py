"""Network capture for the executor (U7, RF-23 / RNF-15).

Installs passive Playwright listeners that record per-request **metadata and
timings only** — NEVER response bodies. Before anything is persisted, the HAR
is filtered to the storefront's own domain (third-party hosts dropped) and auth
headers / cookies are redacted, and credential-looking query params are stripped
from URLs (RNF-15, blocking).

The data methods (``record_response`` / ``record_failure`` / ``to_har_dict`` /
``build_summary``) are pure and unit-tested directly; ``install`` is the
best-effort adapter wiring real Playwright events to them.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from src.models import ControllerTiming, NetworkSummary, WebVitals

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Header names redacted before persistence (case-insensitive) — RNF-15 / D12.
_REDACTED_HEADERS = frozenset({"authorization", "cookie", "set-cookie", "proxy-authorization"})

# Query-param keys whose values look like credentials — stripped from HAR URLs.
_CREDENTIAL_PARAM = re.compile(
    r"(pass(word)?|token|secret|api[-_]?key|auth|sig|signature|session)", re.IGNORECASE
)


@dataclass
class RequestRecord:
    """One captured request — metadata + timings, no body."""

    url: str
    method: str
    status: int
    resource_type: str
    duration_ms: int
    size: int
    failed: bool = False
    headers: dict[str, str] = field(default_factory=dict)


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Drop auth/cookie headers; keep the rest (values of dropped keys never leak)."""
    return {k: v for k, v in headers.items() if k.lower() not in _REDACTED_HEADERS}


def _strip_credentials(url: str) -> str:
    """Remove credential-looking query params from *url* (keeps the rest)."""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    kept = [(k, v) for k, v in parse_qsl(parsed.query) if not _CREDENTIAL_PARAM.search(k)]
    return urlunparse(parsed._replace(query=urlencode(kept)))


class NetworkCapture:
    """Records storefront requests for one flow; emits a redacted HAR + summary."""

    def __init__(self, store_url: str) -> None:
        self._host = (urlparse(store_url).hostname or "").lower()
        self.records: list[RequestRecord] = []

    # -- allowlist ---------------------------------------------------------

    def host_allowed(self, url: str) -> bool:
        """True if *url*'s host is the storefront host (or a subdomain of it)."""
        host = (urlparse(url).hostname or "").lower()
        if not self._host or not host:
            return False
        return host == self._host or host.endswith("." + self._host)

    # -- recording (pure; unit-tested directly) ---------------------------

    def record_response(
        self,
        *,
        url: str,
        method: str,
        status: int,
        resource_type: str,
        duration_ms: int,
        size: int = 0,
        headers: dict[str, str] | None = None,
    ) -> None:
        if not self.host_allowed(url):
            return  # third-party host — dropped from the capture
        self.records.append(
            RequestRecord(
                url=url,
                method=method,
                status=status,
                resource_type=resource_type,
                duration_ms=max(0, duration_ms),
                size=max(0, size),
                failed=status >= 400,
                headers=headers or {},
            )
        )

    def record_failure(
        self, *, url: str, method: str, resource_type: str
    ) -> None:
        if not self.host_allowed(url):
            return
        self.records.append(
            RequestRecord(
                url=url,
                method=method,
                status=0,
                resource_type=resource_type,
                duration_ms=0,
                size=0,
                failed=True,
            )
        )

    def reset(self) -> None:
        """Clear records — used to segment capture per flow in a composition."""
        self.records = []

    # -- serialization -----------------------------------------------------

    def to_har_dict(self) -> dict[str, Any]:
        """Return a HAR-shaped dict: metadata + timings only, fully redacted."""
        entries: list[dict[str, Any]] = []
        for rec in self.records:
            entries.append(
                {
                    "request": {
                        "method": rec.method,
                        "url": _strip_credentials(rec.url),
                        "headers": [
                            {"name": k, "value": v}
                            for k, v in _redact_headers(rec.headers).items()
                        ],
                        # No postData / body is ever captured (RNF-15).
                    },
                    "response": {"status": rec.status, "bodySize": -1, "content": {}},
                    "timings": {"wait": rec.duration_ms},
                    "_resourceType": rec.resource_type,
                }
            )
        return {
            "log": {
                "version": "1.2",
                "creator": {"name": "TestPilot SFCC", "version": "u7"},
                "entries": entries,
            }
        }

    def build_summary(
        self,
        *,
        controllers: list[ControllerTiming],
        web_vitals: WebVitals | None,
        har_url: str | None,
    ) -> NetworkSummary:
        """Assemble the ``NetworkSummary`` for the current records."""
        return NetworkSummary(
            total_requests=len(self.records),
            failed_requests=sum(1 for r in self.records if r.failed),
            controllers=controllers,
            web_vitals=web_vitals,
            har_url=har_url,
        )

    # -- best-effort Playwright wiring (not unit-tested vs a real browser) -

    def install(self, page: "Page") -> None:
        """Wire Playwright ``response``/``requestfailed`` events to the recorders."""

        def _on_response(response: Any) -> None:
            try:
                request = response.request
                timing = getattr(request, "timing", None) or {}
                start = timing.get("requestStart", 0) or 0
                end = timing.get("responseEnd", 0) or 0
                duration = int(end - start) if end >= start else 0
                self.record_response(
                    url=response.url,
                    method=request.method,
                    status=response.status,
                    resource_type=getattr(request, "resource_type", "other"),
                    duration_ms=duration,
                    headers=dict(getattr(request, "headers", {}) or {}),
                )
            except Exception as exc:  # noqa: BLE001 — capture must never break a run
                logger.debug("response capture skipped: %s", type(exc).__name__)

        def _on_failed(request: Any) -> None:
            try:
                self.record_failure(
                    url=request.url,
                    method=request.method,
                    resource_type=getattr(request, "resource_type", "other"),
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("failure capture skipped: %s", type(exc).__name__)

        page.on("response", _on_response)
        page.on("requestfailed", _on_failed)
