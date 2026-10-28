"""Opper application attribution settings."""

OPPER_APP_NAME = "openfic"


def get_opper_attribution_headers() -> dict[str, str]:
    """Return headers used to attribute requests to OpenFic in Opper."""
    return {
        "X-Opper-Name": OPPER_APP_NAME,
    }
