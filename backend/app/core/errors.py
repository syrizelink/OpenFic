"""
Domain-specific errors.
"""


class OpenFicError(Exception):
    """Base exception for OpenFic."""

    pass


class ProviderError(OpenFicError):
    """Error from model provider."""

    error_type: str = "provider_error"
    status_code: int = 500


class RateLimitError(ProviderError):
    """Provider rate limit exceeded."""

    error_type = "provider_rate_limit"
    status_code = 429


class ProviderAuthError(ProviderError):
    """Provider authentication error."""

    error_type = "provider_auth"
    status_code = 401


class ProviderTimeoutError(ProviderError):
    """Provider request timed out."""

    error_type = "provider_timeout"
    status_code = 504


class LLMTimeoutError(ProviderTimeoutError):
    """Pemanggilan LLM melewati batas waktu."""

    pass


class AgentTimeoutError(OpenFicError):
    """Agent execution timed out."""

    pass


class StorageError(OpenFicError):
    """Storage/persistence error."""

    pass


class NotFoundError(OpenFicError):
    """Kesalahan sumber daya tidak ditemukan."""

    pass


class ValidationError(OpenFicError):
    """Kesalahan validasi."""

    pass


class ConflictError(OpenFicError):
    """Kesalahan konflik sumber daya."""

    pass


class ProjectAlreadyBoundError(OpenFicError):
    """Kesalahan proyek sudah terikat ke buku dunia."""

    pass


class WorldInfoExistsError(OpenFicError):
    """Kesalahan buku dunia sudah ada."""

    pass
