"""MartLLM application attribution settings."""

MARTLLM_APP_URL = "https://github.com/syrizelink/OpenFic"
MARTLLM_APP_TITLE = "OpenFic"


def get_martllm_attribution_headers() -> dict[str, str]:
    """Return headers used to attribute requests to OpenFic in MartLLM."""
    return {
        "HTTP-Referer": MARTLLM_APP_URL,
        "X-Title": MARTLLM_APP_TITLE,
    }
