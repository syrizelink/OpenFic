from app.agent_runtime.types import TerminationCondition, ReactAgentConfig
from app.agent_runtime.graph.state import AgentRuntimeState
from app.agent_runtime.graph.orchestrator.state import OrchestratorState


def test_termination_condition_tool_success():
    tc = TerminationCondition(mode="tool_success", tool_name="dispatch_subagent")
    assert tc.mode == "tool_success"
    assert tc.tool_name == "dispatch_subagent"


def test_termination_condition_no_tool_call():
    tc = TerminationCondition(mode="no_tool_call")
    assert tc.mode == "no_tool_call"
    assert tc.tool_name is None


def test_react_agent_config_defaults():
    tc = TerminationCondition(mode="no_tool_call")
    config = ReactAgentConfig(
        name="test_agent",
        tools=[],
        termination=tc,
    )
    assert config.max_iterations == 1000


def test_agent_runtime_state_is_valid_typed_dict():
    state: AgentRuntimeState = {
        "session_id": "sess_001",
        "task_id": "task_001",
        "project_id": "proj_001",
        "model_config": {"provider_type": "openai", "model_id": "gpt-4o", "api_key": "sk-test", "base_url": ""},
        "active_agent": None,
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "user_request": "test request",
        "installed_skill_ids": [],
        "current_revision_id": "rev_001",
    }
    assert state["session_id"] == "sess_001"
    assert "handoff_context" not in state


def test_orchestrator_state_extends_agent_runtime_state():
    state: OrchestratorState = {
        "session_id": "sess_001",
        "task_id": "task_001",
        "project_id": "proj_001",
        "model_config": {"provider_type": "openai", "model_id": "gpt-4o", "api_key": "sk-test", "base_url": ""},
        "active_agent": "explorer",
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "user_request": "rewrite chapter 3",
        "installed_skill_ids": [],
        "current_revision_id": "rev_001",
        "parent_thread_id": "sess_001",
    }
    assert state["active_agent"] == "explorer"
    assert state["parent_thread_id"] == "sess_001"
    assert "handoff_context" not in state
