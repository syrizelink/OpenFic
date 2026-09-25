"""Requesty application attribution settings."""

REQUESTY_APP_URL = "https://github.com/syrizelink/OpenFic"
REQUESTY_APP_TITLE = "OpenFic"


def get_requesty_attribution_headers() -> dict[str, str]:
    """Return headers used to attribute requests to OpenFic in Requesty."""
    return {
        "HTTP-Referer": REQUESTY_APP_URL,
        "X-Title": REQUESTY_APP_TITLE,
    }
