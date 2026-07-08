from typing import TypedDict


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
    current_revision_id: str | None