"""FastAPI application layer for TestPilot SFCC — U4.

The app is built by ``create_app`` in ``src.api.app``. NL translation
(``/v1/translate`` + ``src/agents/``) is wave 2 (U8) and not part of this package.
"""

from src.api.app import create_app

__all__ = ["create_app"]
