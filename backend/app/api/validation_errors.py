import httpx


def format_validation_error(error: Exception) -> str:
    """Keep the exception reason and provider response available to the UI."""
    detail = f"{type(error).__name__}: {error}".rstrip()
    if isinstance(error, httpx.HTTPStatusError) and error.response.text.strip():
        detail = f"{detail}\n{error.response.text.strip()}"
    return detail
