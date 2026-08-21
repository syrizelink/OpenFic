from typing import Any, NotRequired, TypedDict


class AgentRuntimeState(TypedDict):
    session_id: str
    task_id: str
    project_id: str
    model_config: dict
    active_agent: str | None
    agent_key: str
    is_completed: bool
    error: str | None
    retry_count: int
    user_request: str
    user_attachments: list[dict[str, Any]]
    current_revision_id: str | None
    referenced_skill_ids: NotRequired[list[str]]
