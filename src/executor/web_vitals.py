"""Core Web Vitals collection (U7, H8.2 / RNF-15).

Injects a small script that reads LCP/CLS via PerformanceObserver and TTFB via
the Navigation Timing API. Collection is **best-effort**: any failure (no support,
timeout, evaluate error) returns ``None`` and NEVER raises — a flow must never
fail because Web Vitals could not be captured.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.models import WebVitals

if TYPE_CHECKING:
    from playwright.async_api import Page

# Reads metrics already buffered by the browser. LCP/CLS come from buffered
# PerformanceObserver entries; TTFB from the navigation timing entry.
_WEB_VITALS_JS = """
() => {
  try {
    const nav = performance.getEntriesByType('navigation')[0];
    const ttfb = nav ? Math.round(nav.responseStart) : null;
    const lcpEntries = performance.getEntriesByType('largest-contentful-paint');
    const lcp = lcpEntries.length
      ? Math.round(lcpEntries[lcpEntries.length - 1].startTime)
      : null;
    let cls = 0;
    for (const e of performance.getEntriesByType('layout-shift')) {
      if (!e.hadRecentInput) cls += e.value;
    }
    return { lcp_ms: lcp, cls: cls, ttfb_ms: ttfb };
  } catch (e) {
    return null;
  }
}
"""


def _as_int(value: Any) -> int | None:
    try:
        return None if value is None else max(0, int(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return None if value is None else max(0.0, float(value))
    except (TypeError, ValueError):
        return None


async def collect_web_vitals(page: "Page") -> WebVitals | None:
    """Return ``WebVitals`` for the current page, or ``None`` if unavailable."""
    try:
        raw = await page.evaluate(_WEB_VITALS_JS)
    except Exception:  # noqa: BLE001 — never fail a flow over CWV (RNF-15)
        return None
    if not raw or not isinstance(raw, dict):
        return None
    return WebVitals(
        lcp_ms=_as_int(raw.get("lcp_ms")),
        cls=_as_float(raw.get("cls")),
        ttfb_ms=_as_int(raw.get("ttfb_ms")),
    )
