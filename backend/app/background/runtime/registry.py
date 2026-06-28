"""Background job definition registry."""

from app.background.jobs.base import JobDefinition


class JobRegistry:
    """Maps job type names to discoverable definitions."""

    def __init__(self) -> None:
        self._definitions: dict[str, JobDefinition] = {}

    def register(self, definition: JobDefinition) -> None:
        if definition.type in self._definitions:
            existing = self._definitions[definition.type]
            if existing == definition:
                return
            raise ValueError(f"后台任务类型重复注册: {definition.type}")
        self._definitions[definition.type] = definition

    def get(self, job_type: str) -> JobDefinition | None:
        return self._definitions.get(job_type)

    def list_definitions(self) -> list[JobDefinition]:
        return list(self._definitions.values())

    def clear(self) -> None:
        self._definitions.clear()


_registry = JobRegistry()


def get_job_registry() -> JobRegistry:
    return _registry
