class ContextBuildError(Exception):
    """上下文构建失败的统一异常。"""

    def __init__(self, part: str, reason: str, cause: Exception | None = None):
        self.part = part
        self.reason = reason
        self.cause = cause
        super().__init__(f"[context:{part}] {reason}")
