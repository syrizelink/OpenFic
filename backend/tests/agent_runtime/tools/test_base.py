import json
import pytest
from pydantic import BaseModel
from unittest.mock import patch
from typing import Literal

from app.agent_runtime.tools.base import AgentTool, HookContext, HookResult
from app.agent_runtime.tools.errors import normalize_tool_failure_result


class DummyInput(BaseModel):
    value: str


class DummyTool(AgentTool):
    name: str = "dummy"
    description: str = "A dummy tool for testing"
    access_level: str = "readonly"
    args_schema: type[BaseModel] = DummyInput

    async def _execute(self, value: str) -> str:
        return f"executed:{value}"


class RefInput(BaseModel):
    type: Literal["order", "title"]


class ComplexInput(BaseModel):
    volume_ref: RefInput
    chapter_ref: RefInput


class ComplexValidationTool(AgentTool):
    name: str = "complex_validation"
    description: str = "A tool with nested validation errors"
    args_schema: type[BaseModel] = ComplexInput

    async def _execute(self, volume_ref: RefInput, chapter_ref: RefInput) -> str:
        return "ok"


class PreviewTool(AgentTool):
    name: str = "preview"
    description: str = "A tool with approval preview"
    access_level: str = "write"
    args_schema: type[BaseModel] = DummyInput

    async def build_interrupt_preview(self, args: dict[str, object]) -> dict | None:
        return {
            "type": "preview",
            "success": True,
            "data": {"value": args.get("value")},
        }

    async def _execute(self, value: str) -> str:
        return f"executed:{value}"


class FailingTool(AgentTool):
    name: str = "failing"
    description: str = "A tool that raises"
    args_schema: type[BaseModel] = DummyInput

    async def _execute(self, value: str) -> str:
        from app.agent_runtime.tools.errors import ToolExecutionError
        raise ToolExecutionError("something went wrong", code="not_found")


class UnexpectedFailingTool(AgentTool):
    name: str = "unexpected_failing"
    description: str = "A tool with an unexpected exception"
    args_schema: type[BaseModel] = DummyInput

    async def _execute(self, value: str) -> str:
        raise RuntimeError("database password=super-secret")


class LegacyFailingTool(AgentTool):
    name: str = "legacy_failing"
    description: str = "A tool with a legacy error result"
    args_schema: type[BaseModel] = DummyInput

    async def _execute(self, value: str) -> str:
        return json.dumps(
            {
                "error": "something went wrong",
                "metadata": {"trace": "legacy diagnostic detail"},
            }
        )


def _make_state() -> dict:
    return {
        "session_id": "sess-1",
        "project_id": "proj-1",
        "model_config": {},
        "active_agent": None,
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "message_checkpoints": [],
        "user_request": "",
    }


async def test_agent_tool_execute_success():
    tool = DummyTool(_state=_make_state())
    result = await tool.ainvoke({"value": "hello"})
    assert result == "executed:hello"


async def test_agent_tool_project_id_from_state():
    tool = DummyTool(_state=_make_state())
    assert tool.project_id == "proj-1"
    assert tool.session_id == "sess-1"


async def test_agent_tool_execution_error_returns_safe_failure_result():
    tool = FailingTool(_state=_make_state())
    result = await tool.ainvoke({"value": "test"})
    assert json.loads(result) == {
        "type": "fail",
        "success": False,
        "code": "not_found",
        "message": "something went wrong",
    }


async def test_agent_tool_execution_error_logs_exception_traceback():
    tool = FailingTool(_state=_make_state())

    with patch("app.agent_runtime.tools.errors.logger") as logger:
        await tool.ainvoke({"value": "test"})

    bound_logger = logger.bind.return_value
    bound_logger.opt.assert_called_once()
    assert isinstance(bound_logger.opt.call_args.kwargs["exception"], Exception)
    bound_logger.opt.return_value.error.assert_called_once_with(
        "Agent 工具执行失败"
    )


async def test_agent_tool_preserves_unexpected_exception_message_and_logs_exception():
    tool = UnexpectedFailingTool(_state=_make_state())

    with patch("app.agent_runtime.tools.errors.logger") as logger:
        result = await tool.ainvoke({"value": "test"})

    bound_logger = logger.bind.return_value
    bound_logger.opt.assert_called_once()
    bound_logger.opt.return_value.error.assert_called_once_with("Agent 工具执行失败")
    logged_exception = bound_logger.opt.call_args.kwargs["exception"]
    assert isinstance(logged_exception, RuntimeError)
    payload = json.loads(result)
    assert payload == {
        "type": "fail",
        "success": False,
        "code": "execution_failed",
        "message": "工具执行异常: database password=super-secret",
    }


async def test_agent_tool_validation_error_returns_safe_failure_result():
    tool = DummyTool(_state=_make_state())
    result = await tool.ainvoke({"wrong_field": 123})
    payload = json.loads(result)
    assert payload["type"] == "fail"
    assert payload["success"] is False
    assert payload["code"] == "validation_error"
    assert "参数校验失败" in payload["message"]
    assert "trace" not in payload


async def test_agent_tool_validation_error_is_logged():
    tool = DummyTool(_state=_make_state())

    with patch("app.agent_runtime.tools.errors.logger") as logger:
        await tool.ainvoke({"wrong_field": 123})

    bound_logger = logger.bind.return_value
    bound_logger.warning.assert_called_once()
    assert "参数校验失败" in str(bound_logger.warning.call_args.args)


async def test_agent_tool_validation_error_omits_repeated_pydantic_help_urls():
    tool = ComplexValidationTool(_state=_make_state())

    result = await tool.ainvoke(
        {
            "volume_ref": {"type": 123},
            "chapter_ref": {"type": "invalid_type"},
        }
    )
    message = json.loads(result)["message"]

    assert "volume_ref.type" in message
    assert "chapter_ref.type" in message
    assert "Input should be 'order' or 'title'" in message
    assert "For further information visit" not in message
    assert "https://errors.pydantic.dev" not in message


async def test_agent_tool_normalizes_legacy_error_result():
    tool = LegacyFailingTool(_state=_make_state())
    with patch("app.agent_runtime.tools.errors.logger") as logger:
        result = await tool.ainvoke({"value": "test"})

    assert json.loads(result) == {
        "type": "fail",
        "success": False,
        "code": "execution_failed",
        "message": "something went wrong",
    }
    warning_args = logger.bind.return_value.warning.call_args.args
    assert "legacy diagnostic detail" in str(warning_args)


def test_normalize_tool_failure_result_caches_parsed_payload() -> None:
    result, failure = normalize_tool_failure_result(
        '{"success":true,"items":[{"id":"chapter-1"}]}'
    )

    assert failure is None
    assert getattr(result, "payload") == {
        "success": True,
        "items": [{"id": "chapter-1"}],
    }


async def test_agent_tool_pre_hook_can_block():
    async def blocking_hook(ctx: HookContext) -> HookResult:
        return HookResult(proceed=False, interrupt_payload={"type": "test"})

    tool = DummyTool(_state=_make_state(), _pre_hooks=[blocking_hook])
    with pytest.raises(Exception):
        await tool.ainvoke({"value": "hello"})


async def test_agent_tool_builds_tool_preview_for_tool_approval_interrupt():
    async def blocking_hook(ctx: HookContext) -> HookResult:
        return HookResult(
            proceed=False,
            interrupt_payload={
                "type": "tool_approval",
                "tool_name": ctx.tool_name,
                "args": ctx.args,
            },
        )

    tool = PreviewTool(_state=_make_state(), _pre_hooks=[blocking_hook])
    captured: list[dict] = []

    def fake_interrupt(payload: dict) -> None:
        captured.append(payload)
        raise RuntimeError("interrupted")

    with patch("langgraph.types.interrupt", side_effect=fake_interrupt):
        with pytest.raises(RuntimeError, match="interrupted"):
            await tool.ainvoke(
                {"value": "hello"},
                config={"metadata": {"tool_call_id": "call-1"}},
            )

    assert captured[0]["tool_call_id"] == "call-1"
    assert captured[0]["tool_result_preview"] == {
        "type": "preview",
        "success": True,
        "data": {"value": "hello"},
    }


async def test_agent_tool_does_not_execute_after_rejected_tool_approval():
    executed: list[str] = []

    class GuardedTool(PreviewTool):
        async def _execute(self, value: str) -> str:
            executed.append(value)
            return f"executed:{value}"

    async def blocking_hook(ctx: HookContext) -> HookResult:
        return HookResult(
            proceed=False,
            interrupt_payload={
                "type": "tool_approval",
                "tool_name": ctx.tool_name,
                "args": ctx.args,
            },
        )

    tool = GuardedTool(_state=_make_state(), _pre_hooks=[blocking_hook])

    with patch(
        "langgraph.types.interrupt",
        return_value={
            "action_type": "tool_approval",
            "approval_id": "approval-1",
            "approved": False,
        },
    ):
        result = await tool.ainvoke({"value": "hello"})

    payload = json.loads(result)
    assert payload == {
        "type": "control",
        "success": False,
        "status": "approval_denied",
        "message": "工具调用已被用户拒绝",
        "approval_id": "approval-1",
        "tool_name": "preview",
    }
    assert executed == []


async def test_agent_tool_post_hook_runs_after_execute():
    called = []

    async def post_hook(ctx: HookContext) -> HookResult:
        called.append(ctx.tool_name)
        return HookResult()

    tool = DummyTool(_state=_make_state(), _post_hooks=[post_hook])
    await tool.ainvoke({"value": "hello"})
    assert called == ["dummy"]


async def test_agent_tool_hook_receives_runnable_config_and_tool_call_id():
    captured = []

    async def post_hook(ctx: HookContext) -> HookResult:
        captured.append(ctx)
        return HookResult()

    tool = DummyTool(_state=_make_state(), _post_hooks=[post_hook])

    await tool.ainvoke(
        {"value": "hello"},
        config={
            "metadata": {"tool_call_id": "call-1"},
            "configurable": {"db_session": object()},
        },
    )

    assert captured[0].tool_call_id == "call-1"
    assert captured[0].config["configurable"]["db_session"] is not None


async def test_agent_tool_post_hook_can_rewrite_output():
    async def rewrite_hook(ctx: HookContext) -> HookResult:
        assert ctx.output == "executed:hello"
        return HookResult(
            output=json.dumps(
                {"result_ref": "t1", "value": ctx.output},
                ensure_ascii=False,
            )
        )

    tool = DummyTool(_state=_make_state(), _post_hooks=[rewrite_hook])
    result = await tool.ainvoke({"value": "hello"})

    assert json.loads(result) == {
        "result_ref": "t1",
        "value": "executed:hello",
    }
