from langchain_core.messages import BaseMessage

from app.agent_runtime.graph.state import AgentRuntimeState


class OrchestratorState(AgentRuntimeState, total=False):
    """Parent PA graph state.

    The PA graph intentionally keeps one runtime node. Subagent routing lives in
    persisted AgentChildRun rows and dispatch tool results, not fixed graph edges.
    """

    parent_thread_id: str
    messages: list[BaseMessage]
