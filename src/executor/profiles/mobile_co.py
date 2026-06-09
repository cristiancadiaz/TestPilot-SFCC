"""Browser profile: mobile Colombia (iPhone 15 viewport, es-CO locale)."""

from src.models import BrowserProfile

MOBILE_CO = BrowserProfile(
    name="mobile_co",
    viewport_width=390,
    viewport_height=844,
    locale="es-CO",
    is_mobile=True,
    user_agent=(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15"
    ),
)
