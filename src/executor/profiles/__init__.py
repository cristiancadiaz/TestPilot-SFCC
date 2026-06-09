"""Browser profile catalogue (catalog v2: exactly 3 profiles).

``mobile_mx`` does NOT exist — it was removed in the scope realignment
(2026-06-03). The catalog is: mobile_co, desktop_co, desktop_ec.
"""

from src.executor.profiles.desktop_co import DESKTOP_CO
from src.executor.profiles.desktop_ec import DESKTOP_EC
from src.executor.profiles.mobile_co import MOBILE_CO
from src.models import BrowserProfile

# Ordered catalog — the runner iterates this list.
ALL_PROFILES: list[BrowserProfile] = [MOBILE_CO, DESKTOP_CO, DESKTOP_EC]

__all__ = ["MOBILE_CO", "DESKTOP_CO", "DESKTOP_EC", "ALL_PROFILES"]
