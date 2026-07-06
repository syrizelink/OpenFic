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
    """LLM调用超时。"""

    pass


class AgentTimeoutError(OpenFicError):
    """Agent execution timed out."""

    pass


class StorageError(OpenFicError):
    """Storage/persistence error."""

    pass


class NotFoundError(OpenFicError):
    """资源不存在错误。"""

    pass


class ValidationError(OpenFicError):
    """验证错误。"""

    pass


class ConflictError(OpenFicError):
    """资源冲突错误。"""

    pass


class ProjectAlreadyBoundError(OpenFicError):
    """项目已绑定世界书错误。"""

    pass


class WorldInfoExistsError(OpenFicError):
    """世界书已存在错误。"""

    pass
