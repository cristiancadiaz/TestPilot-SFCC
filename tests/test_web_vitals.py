"""Tests for src/executor/web_vitals.py (U7, H8.2 / RNF-15).

Collection is best-effort: a supporting page yields populated WebVitals; an
unsupported/erroring page yields None and never raises.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.executor.web_vitals import collect_web_vitals
from src.models import WebVitals


@pytest.mark.asyncio
async def test_populated_when_metrics_available() -> None:
    page = MagicMock()
    page.evaluate = AsyncMock(
        return_value={"lcp_ms": 1200, "cls": 0.05, "ttfb_ms": 300}
    )
    vitals = await collect_web_vitals(page)
    assert isinstance(vitals, WebVitals)
    assert vitals.lcp_ms == 1200
    assert vitals.cls == 0.05
    assert vitals.ttfb_ms == 300


@pytest.mark.asyncio
async def test_none_when_page_returns_nothing() -> None:
    page = MagicMock()
    page.evaluate = AsyncMock(return_value=None)
    assert await collect_web_vitals(page) is None


@pytest.mark.asyncio
async def test_none_and_no_raise_when_evaluate_fails() -> None:
    page = MagicMock()
    page.evaluate = AsyncMock(side_effect=RuntimeError("no PerformanceObserver"))
    # Must NOT raise — a flow never fails because CWV could not be read.
    assert await collect_web_vitals(page) is None


@pytest.mark.asyncio
async def test_partial_metrics_tolerated() -> None:
    page = MagicMock()
    page.evaluate = AsyncMock(return_value={"lcp_ms": None, "cls": 0.0, "ttfb_ms": 210})
    vitals = await collect_web_vitals(page)
    assert vitals is not None
    assert vitals.lcp_ms is None
    assert vitals.ttfb_ms == 210
