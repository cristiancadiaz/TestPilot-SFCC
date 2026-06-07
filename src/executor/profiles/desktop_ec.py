"""Browser profile: desktop Ecuador (1280x800, es-EC locale).

Replaces the pre-realignment ``mobile_mx`` profile. Catalog v2 has exactly
three profiles: mobile_co, desktop_co, desktop_ec.
"""

from src.models import BrowserProfile

DESKTOP_EC = BrowserProfile(
    name="desktop_ec",
    viewport_width=1280,
    viewport_height=800,
    locale="es-EC",
    is_mobile=False,
    user_agent=(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    ),
)
