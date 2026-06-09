"""Executor package — Playwright-based synthetic user runner.

Public API: ``run_profile`` executes a single flow in a single browser profile.
Credentials are always resolved server-side (ADR-001) and passed in via
``ResolvedEnvironment``; the executor never reads secrets itself.
"""

from src.executor.runner import run_profile

__all__ = ["run_profile"]
