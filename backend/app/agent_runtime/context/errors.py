class ContextBuildError(Exception):
    """Exception seragam untuk kegagalan pembangunan konteks."""

    def __init__(self, part: str, reason: str, cause: Exception | None = None):
        self.part = part
        self.reason = reason
        self.cause = cause
        super().__init__(f"[context:{part}] {reason}")
