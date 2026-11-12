"""UberLLM application attribution settings."""

UBERLLM_APP_URL = "https://github.com/syrizelink/OpenFic"
UBERLLM_APP_TITLE = "OpenFic"


def get_uberllm_attribution_headers() -> dict[str, str]:
    """Return headers used to attribute requests to OpenFic in UberLLM."""
    return {
        "HTTP-Referer": UBERLLM_APP_URL,
        "X-Title": UBERLLM_APP_TITLE,
    }
