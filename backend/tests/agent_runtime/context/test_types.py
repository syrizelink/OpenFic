from app.agent_runtime.context.errors import ContextBuildError
from app.agent_runtime.context.types import ContextMessage


def test_context_message_minimal():
    m = ContextMessage(role="system", content="hello")
    assert m.role == "system"
    assert m.content == "hello"
    assert m.name is None
    assert m.tool_call_id is None
    assert m.tool_calls is None
    assert m.metadata is None


def test_context_message_with_metadata():
    m = ContextMessage(role="user", content="x", metadata={"part": "history"})
    assert m.metadata == {"part": "history"}


def test_context_build_error_format():
    err = ContextBuildError("environment", "chapter not found")
    assert err.part == "environment"
    assert err.reason == "chapter not found"
    assert "[context:environment]" in str(err)


def test_context_build_error_with_cause():
    cause = ValueError("db down")
    err = ContextBuildError("rules", "db error", cause=cause)
    assert err.cause is cause
