"""Tests for src/executor/profiles/.

Verifies that:
  - Each profile has the correct field values.
  - ``ALL_PROFILES`` contains exactly 3 profiles with the catalog-v2 names.
  - ``mobile_mx`` does NOT exist.
  - All entries are ``BrowserProfile`` instances.
"""

from __future__ import annotations

import pytest

from src.executor.profiles import ALL_PROFILES, DESKTOP_CO, DESKTOP_EC, MOBILE_CO
from src.models import BrowserProfile


# ---------------------------------------------------------------------------
# Individual profile field checks
# ---------------------------------------------------------------------------


def test_mobile_co_fields() -> None:
    """mobile_co: is_mobile=True, locale=es-CO, 390x844."""
    assert MOBILE_CO.name == "mobile_co"
    assert MOBILE_CO.is_mobile is True
    assert MOBILE_CO.locale == "es-CO"
    assert MOBILE_CO.viewport_width == 390
    assert MOBILE_CO.viewport_height == 844


def test_desktop_co_fields() -> None:
    """desktop_co: is_mobile=False, locale=es-CO, 1440x900."""
    assert DESKTOP_CO.name == "desktop_co"
    assert DESKTOP_CO.is_mobile is False
    assert DESKTOP_CO.locale == "es-CO"
    assert DESKTOP_CO.viewport_width == 1440
    assert DESKTOP_CO.viewport_height == 900


def test_desktop_ec_fields() -> None:
    """desktop_ec: is_mobile=False, locale=es-EC, 1280x800."""
    assert DESKTOP_EC.name == "desktop_ec"
    assert DESKTOP_EC.is_mobile is False
    assert DESKTOP_EC.locale == "es-EC"
    assert DESKTOP_EC.viewport_width == 1280
    assert DESKTOP_EC.viewport_height == 800


# ---------------------------------------------------------------------------
# ALL_PROFILES catalog checks
# ---------------------------------------------------------------------------


def test_all_profiles_has_exactly_3() -> None:
    """Catalog v2 defines exactly 3 profiles."""
    assert len(ALL_PROFILES) == 3


def test_all_profiles_names() -> None:
    """Profile names must be exactly the catalog-v2 set (no mobile_mx)."""
    names = {p.name for p in ALL_PROFILES}
    assert names == {"mobile_co", "desktop_co", "desktop_ec"}
    assert "mobile_mx" not in names


def test_all_profiles_order() -> None:
    """ALL_PROFILES follows the declared order: mobile_co, desktop_co, desktop_ec."""
    assert ALL_PROFILES[0].name == "mobile_co"
    assert ALL_PROFILES[1].name == "desktop_co"
    assert ALL_PROFILES[2].name == "desktop_ec"


def test_profiles_are_browser_profile_instances() -> None:
    """Every entry in ALL_PROFILES is a BrowserProfile instance."""
    for profile in ALL_PROFILES:
        assert isinstance(profile, BrowserProfile), (
            f"{profile!r} is not a BrowserProfile"
        )


def test_mobile_mx_does_not_exist() -> None:
    """mobile_mx was removed in scope realignment v2 — must not be importable."""
    import importlib

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("src.executor.profiles.mobile_mx")
