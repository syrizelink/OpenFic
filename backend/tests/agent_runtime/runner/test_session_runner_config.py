import pytest

from app.agent_runtime.context import ContextBuildError
from app.agent_runtime.runner.session_runner import SessionRunner


def test_missing_max_context_tokens_raises() -> None:
    with pytest.raises(ContextBuildError) as exc:
        SessionRunner(
            session_id="s1",
            task_id="task_test",
            model_config={},
            project_id="p1",
        )
    assert exc.value.part == "config"


def test_zero_max_context_tokens_raises() -> None:
    with pytest.raises(ContextBuildError) as exc:
        SessionRunner(
            session_id="s1",
            task_id="task_test",
            model_config={"max_context_tokens": 0},
            project_id="p1",
        )
    assert exc.value.part == "config"


def test_valid_config_constructs_ok() -> None:
    runner = SessionRunner(
        session_id="s1",
        task_id="task_test",
        model_config={"max_context_tokens": 8000},
        project_id="p1",
    )
    assert runner.session_id == "s1"
