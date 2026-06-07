"""Browser profile: desktop Colombia (1440x900, es-CO locale)."""

from src.models import BrowserProfile

DESKTOP_CO = BrowserProfile(
    name="desktop_co",
    viewport_width=1440,
    viewport_height=900,
    locale="es-CO",
    is_mobile=False,
    user_agent=(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    ),
)
