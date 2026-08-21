"""OpenRouter application attribution settings."""

OPENROUTER_APP_URL = "https://github.com/syrizelink/OpenFic"
OPENROUTER_APP_TITLE = "OpenFic"
OPENROUTER_APP_CATEGORIES = ("creative-writing", "writing-assistant")


def get_openrouter_attribution_headers() -> dict[str, str]:
    """Return headers used to attribute requests to OpenFic in OpenRouter."""
    return {
        "HTTP-Referer": OPENROUTER_APP_URL,
        "X-OpenRouter-Title": OPENROUTER_APP_TITLE,
        "X-OpenRouter-Categories": ",".join(OPENROUTER_APP_CATEGORIES),
    }
