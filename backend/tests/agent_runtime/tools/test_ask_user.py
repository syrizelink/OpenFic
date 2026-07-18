import json
from unittest.mock import patch

import pytest


def _make_state() -> dict:
    return {
        "session_id": "s1",
        "project_id": "proj-1",
        "model_config": {},
        "active_agent": None,
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "message_checkpoints": [],
        "user_request": "",
    }


def _valid_input() -> dict:
    return {
        "questions": [
            {
                "title": "风格选择",
                "description": "你希望用什么风格？",
                "options": [
                    {"label": "正式", "description": "正式严肃的风格"},
                    {"label": "轻松", "description": "轻松幽默的风格"},
                ],
            }
        ]
    }


class TestAskUser:
    async def test_ask_user_triggers_interrupt(self):
        from langgraph.errors import GraphInterrupt
        from app.agent_runtime.tools.impls.interaction.ask_user import AskUserTool

        tool = AskUserTool(_state=_make_state())

        with patch("app.agent_runtime.tools.impls.interaction.ask_user.interrupt") as mock_interrupt:
            mock_interrupt.side_effect = GraphInterrupt(())
            with pytest.raises(GraphInterrupt):
                await tool.ainvoke(_valid_input())

        mock_interrupt.assert_called_once()
        payload = mock_interrupt.call_args[0][0]
        assert payload["type"] == "ask_user"
        assert len(payload["questions"]) == 1
        serialized_payload = json.loads(json.dumps(payload))
        assert serialized_payload["questions"] == _valid_input()["questions"]

    async def test_ask_user_returns_response_after_resume(self):
        from app.agent_runtime.tools.impls.interaction.ask_user import AskUserTool

        tool = AskUserTool(_state=_make_state())
        interrupt_response = {
            "action_type": "clarification",
            "action_id": "question-1",
            "answer": [{"question": "风格选择", "answer": "正式"}],
        }

        with patch("app.agent_runtime.tools.impls.interaction.ask_user.interrupt") as mock_interrupt:
            mock_interrupt.return_value = interrupt_response
            result = await tool.ainvoke(_valid_input())

        data = json.loads(result)
        assert data == interrupt_response["answer"]

    async def test_ask_user_accepts_more_than_five_questions(self):
        from app.agent_runtime.tools.impls.interaction.ask_user import AskUserTool

        tool = AskUserTool(_state=_make_state())
        tool_input = {
            "questions": [
                {
                    "title": f"Q{i}",
                    "description": "desc",
                    "options": [
                        {"label": "A", "description": "a"},
                        {"label": "B", "description": "b"},
                    ],
                }
                for i in range(6)
            ]
        }
        interrupt_response = {
            "action_type": "clarification",
            "action_id": "question-1",
            "answer": [{"question": "Q0", "answer": "A"}],
        }

        with patch("app.agent_runtime.tools.impls.interaction.ask_user.interrupt") as mock_interrupt:
            mock_interrupt.return_value = interrupt_response
            result = await tool.ainvoke(tool_input)

        assert json.loads(result) == interrupt_response["answer"]
        assert len(mock_interrupt.call_args[0][0]["questions"]) == 6

    async def test_ask_user_accepts_more_than_three_options(self):
        from app.agent_runtime.tools.impls.interaction.ask_user import AskUserTool

        tool = AskUserTool(_state=_make_state())
        tool_input = {
            "questions": [
                {
                    "title": "Q",
                    "description": "desc",
                    "options": [
                        {"label": "A", "description": "a"},
                        {"label": "B", "description": "b"},
                        {"label": "C", "description": "c"},
                        {"label": "D", "description": "d"},
                    ],
                }
            ]
        }
        interrupt_response = {
            "action_type": "clarification",
            "action_id": "question-1",
            "answer": [{"question": "Q", "answer": "D"}],
        }

        with patch("app.agent_runtime.tools.impls.interaction.ask_user.interrupt") as mock_interrupt:
            mock_interrupt.return_value = interrupt_response
            result = await tool.ainvoke(tool_input)

        assert json.loads(result) == interrupt_response["answer"]
        assert len(mock_interrupt.call_args[0][0]["questions"][0]["options"]) == 4
