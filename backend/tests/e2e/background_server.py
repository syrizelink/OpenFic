"""Real OpenFic server with a scripted OpenAI-compatible HTTP provider.

Run through the isolated Playwright configs. Runtime/model factory,
database, tools, approvals, socket events, and persistence use real implementations.
The reliability suite can inject a failure at the board-notice query boundary.
All control endpoints live exclusively in this test executable.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

# Set these before importing application settings. Never read a user's data.
test_data_dir = os.environ.get("OPENFIC_E2E_DATA_DIR") or tempfile.mkdtemp(
    prefix="openfic-e2e-subagents-"
)
if not Path(test_data_dir).name.startswith("openfic-e2e-subagents-"):
    raise RuntimeError("E2E server requires an isolated test directory")
os.environ["OPENFIC_E2E_DATA_DIR"] = test_data_dir
os.environ["OPENFIC_DATA_DIR"] = test_data_dir
os.environ["OPENFIC_DATABASE_BACKEND"] = "sqlite"
os.environ["OPENFIC_DATABASE_URL"] = ""
os.environ["OPENFIC_CHECKPOINT_DATABASE_URL"] = ""
os.environ["OPENFIC_AUTH_PASSWORD"] = ""
os.environ["BACKGROUND_WORKER_ENABLED"] = "false"
os.environ["POSTHOG_API_KEY"] = ""
os.environ["LLM_RETRY_MAX_ATTEMPTS"] = "2"
os.environ["LLM_RETRY_BASE_INTERVAL"] = "0.05"
os.environ["LLM_RETRY_MAX_INTERVAL"] = "0.1"
os.environ["LLM_EMPTY_RESPONSE_RETRIES"] = "1"

from fastapi import APIRouter, HTTPException, Request  # noqa: E402
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: E402
from loguru import logger  # noqa: E402
from sqlalchemy import select  # noqa: E402
import uvicorn  # noqa: E402

from app.main import app, fastapi_app  # noqa: E402
from app.agent_runtime import agent_board  # noqa: E402
from app.agent_runtime.persistence.model import (  # noqa: E402
    AgentChildRun,
    AgentChildRunRequest,
    AgentRunMessage,
)
from app.agent_runtime.runner.run_registry import get_agent_run_registry  # noqa: E402
from app.storage.database import create_session  # noqa: E402
from app.storage.models.note import Note  # noqa: E402
from app.storage.models.task import Task  # noqa: E402
from app.storage.models.revision import Revision  # noqa: E402


@dataclass
class Scenario:
    script: dict[str, Any]
    cursors: dict[str, int] = field(default_factory=dict)
    gates: dict[str, asyncio.Event] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)
    error_offset: int = 0


scenarios: dict[str, Scenario] = {}
checkpoint_errors: list[str] = []


def record_checkpoint_error(message):
    record = message.record
    if record["level"].no >= 40 and (
        "prune" in record["function"] or "checkpointer" in record["name"]
    ):
        checkpoint_errors.append(record["message"])


logger.add(record_checkpoint_error, level="ERROR")
router = APIRouter(prefix="/api/v1/__e2e__")
board_notice_unavailable = False
original_board_notice = agent_board.board_notice


async def faultable_board_notice(session, scope):
    if board_notice_unavailable:
        raise RuntimeError("Injected board-notice query failure")
    return await original_board_notice(session, scope)


agent_board.board_notice = faultable_board_notice


@router.post("/board-notice-failure")
async def board_notice_failure(body: dict):
    global board_notice_unavailable
    board_notice_unavailable = body.get("enabled") is True
    return {"enabled": board_notice_unavailable}


@router.get("/health")
async def health():
    return {"ready": True, "isolated": True}


@router.post("/scenarios/{scenario_id}")
async def configure(scenario_id: str, body: dict):
    if scenario_id in scenarios:
        raise HTTPException(409, "Scenario IDs must be unique")
    scenarios[scenario_id] = Scenario(body, error_offset=len(checkpoint_errors))
    return {"id": scenario_id}


@router.post("/scenarios/{scenario_id}/release/{gate}")
async def release(scenario_id: str, gate: str):
    scenario = scenarios[scenario_id]
    scenario.gates.setdefault(gate, asyncio.Event()).set()
    return {"released": gate}


@router.post("/restart")
async def restart():
    """Simulate a process crash/restart, retaining this test's SQLite databases."""

    async def replace_process():
        await asyncio.sleep(0.2)
        os.execv(sys.executable, [sys.executable, "-m", "tests.e2e.background_server"])

    asyncio.create_task(replace_process())
    return {"restarting": True}


def expand(value: Any, messages: list[dict]) -> Any:
    """Resolve script references using actual tool results sent to the model."""
    if isinstance(value, dict):
        return {key: expand(item, messages) for key, item in value.items()}
    if isinstance(value, list):
        return [expand(item, messages) for item in value]
    if isinstance(value, str) and value.startswith("$dispatch:"):
        call_id = value.split(":", 1)[1]
        for message in messages:
            if message.get("role") == "tool" and message.get("tool_call_id") == call_id:
                payload = json.loads(message["content"])
                return payload["dispatch_id"]
        raise ValueError(f"No real dispatch result for {call_id}")
    if isinstance(value, str) and value.startswith("$board:"):
        index = int(value.split(":", 1)[1])
        for message in reversed(messages):
            if message.get("role") == "tool":
                payload = json.loads(message["content"])
                if isinstance(payload, dict) and isinstance(payload.get("messages"), list) and payload["messages"]:
                    return payload["messages"][index]["id"]
        raise ValueError("No real board_read message to reply to")
    return value


@router.post("/model/v1/chat/completions")
async def completion(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    serialized = json.dumps(messages, ensure_ascii=False)
    matches = re.findall(r"E2E_SCENARIO:([a-zA-Z0-9_-]+)", serialized)
    if not matches or matches[-1] not in scenarios:
        return JSONResponse(
            {"error": {"message": "Unscripted model request"}}, status_code=400
        )
    scenario_id = matches[-1]
    scenario = scenarios[scenario_id]
    parent = any(
        tool.get("function", {}).get("name") == "dispatch_subagent"
        for tool in body.get("tools", [])
    )
    child_matches = re.findall(
        r"E2E_CHILD:([a-zA-Z0-9_-]+)",
        json.dumps(
            [message for message in messages if message.get("role") == "user"],
            ensure_ascii=False,
        ),
    )
    actor = "parent" if parent else child_matches[-1] if child_matches else "unknown"
    cursor = scenario.cursors.get(actor, 0)
    steps = scenario.script.get("parent" if parent else "children", [])
    if not parent:
        steps = steps.get(actor, [])
    record = {
        "actor": actor,
        "step": cursor,
        "messages": messages,
        "started": time.monotonic(),
    }
    scenario.calls.append(record)
    if cursor >= len(steps):
        record["unexpected"] = True
        return JSONResponse(
            {"error": {"message": f"Unscripted {actor} step {cursor}"}}, status_code=500
        )
    step = steps[cursor]
    scenario.cursors[actor] = cursor + 1
    if step.get("http_status"):
        record["http_status"] = step["http_status"]
        return JSONResponse(
            {"error": {"message": step.get("error", "Injected provider failure")}},
            status_code=step["http_status"],
        )
    try:
        tools = expand(step.get("tools", []), messages)
    except (ValueError, KeyError) as exc:
        record["unexpected"] = str(exc)
        return JSONResponse({"error": {"message": str(exc)}}, status_code=500)
    tool_calls = [
        {
            "id": tool.get("id", f"e2e-{actor}-{cursor}-{index}"),
            "type": "function",
            "function": {
                "name": tool["name"],
                "arguments": json.dumps(tool.get("args", {}), ensure_ascii=False),
            },
        }
        for index, tool in enumerate(tools)
    ]
    text = step.get("text", "")
    if target := step.get("until_results"):
        received = sum(
            str(message.get("content", "")).count("[后台 Subagent 执行结果；")
            for message in messages
        )
        if received < target:
            text = "E2E_WAITING"
            scenario.cursors[actor] = cursor

    def chunk(delta: dict, finish_reason=None):
        return (
            "data: "
            + json.dumps(
                {
                    "id": f"chatcmpl-{scenario_id}-{actor}-{cursor}",
                    "object": "chat.completion.chunk",
                    "created": 1,
                    "model": body["model"],
                    "choices": [
                        {"index": 0, "delta": delta, "finish_reason": finish_reason}
                    ],
                },
                ensure_ascii=False,
            )
            + "\n\n"
        )

    async def stream():
        try:
            yield chunk({"role": "assistant"})
            if step.get("partial_text"):
                yield chunk({"content": step["partial_text"]})
            if gate := step.get("gate"):
                record["gate"] = gate
                await scenario.gates.setdefault(gate, asyncio.Event()).wait()
            if step.get("malformed_stream"):
                yield "data: {invalid json}\n\n"
                return
            for index, tool in enumerate(tool_calls):
                function = tool["function"]
                yield chunk(
                    {
                        "tool_calls": [
                            {
                                "index": index,
                                "id": tool["id"],
                                "type": "function",
                                "function": {"name": function["name"], "arguments": ""},
                            }
                        ]
                    }
                )
                # Exercise fragmented Unicode JSON and parallel tool-call parsing.
                arguments = function["arguments"]
                for offset in range(0, len(arguments), 17):
                    yield chunk(
                        {
                            "tool_calls": [
                                {
                                    "index": index,
                                    "function": {
                                        "arguments": arguments[offset : offset + 17]
                                    },
                                }
                            ]
                        }
                    )
                    await asyncio.sleep(0)
            for offset in range(0, len(text), 13):
                yield chunk({"content": text[offset : offset + 13]})
                await asyncio.sleep(0)
            yield chunk({}, "tool_calls" if tool_calls else "stop")
            yield (
                "data: "
                + json.dumps(
                    {
                        "id": f"usage-{cursor}",
                        "object": "chat.completion.chunk",
                        "created": 1,
                        "model": body["model"],
                        "choices": [],
                        "usage": {
                            "prompt_tokens": 30,
                            "completion_tokens": 12,
                            "total_tokens": 42,
                        },
                    }
                )
                + "\n\n"
            )
            yield "data: [DONE]\n\n"
            record["finished"] = True
        except asyncio.CancelledError:
            record["cancelled"] = True
            raise

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/scenarios/{scenario_id}/state")
async def state(scenario_id: str, session_id: str = ""):
    scenario = scenarios.get(scenario_id)
    if scenario is None:
        raise HTTPException(404, "Scenario not configured in this process")
    session = await create_session()
    try:
        children = (
            (
                await session.execute(
                    select(AgentChildRun).where(
                        AgentChildRun.parent_session_id == session_id
                    )
                )
            )
            .scalars()
            .all()
        )
        requests = (
            (
                await session.execute(
                    select(AgentChildRunRequest)
                    .where(AgentChildRunRequest.parent_session_id == session_id)
                    .order_by(AgentChildRunRequest.seq)
                )
            )
            .scalars()
            .all()
        )
        messages = (
            (
                await session.execute(
                    select(AgentRunMessage)
                    .where(AgentRunMessage.session_id == session_id)
                    .order_by(AgentRunMessage.seq)
                )
            )
            .scalars()
            .all()
        )
        task = (
            await session.execute(
                select(Task).where(Task.agent_session_id == session_id)
            )
        ).scalar_one_or_none()
        notes = (
            (
                await session.execute(
                    select(Note).where(Note.project_id == task.project_id)
                )
            )
            .scalars()
            .all()
            if task
            else []
        )
        revisions = (
            (
                await session.execute(
                    select(Revision).where(Revision.agent_session_id == session_id)
                )
            )
            .scalars()
            .all()
        )
        registry = get_agent_run_registry()
        return {
            "checkpoint_errors": checkpoint_errors[scenario.error_offset :],
            "calls": scenario.calls,
            "children": [
                {
                    **row.model_dump(),
                    "runtime_running": await registry.is_child_running(
                        session_id, row.id
                    ),
                }
                for row in children
            ],
            "requests": [row.model_dump() for row in requests],
            "messages": [row.model_dump() for row in messages],
            "task": task.model_dump() if task else None,
            "notes": [row.model_dump() for row in notes],
            "revisions": [row.model_dump() for row in revisions],
            "parent_running": await registry.is_parent_running(session_id),
        }
    finally:
        await session.close()


# Vite serves the frontend. Ensure test endpoints precede any optional SPA mount.
fastapi_app.router.routes[:] = [
    route
    for route in fastapi_app.router.routes
    if getattr(route, "name", "") != "frontend"
]
fastapi_app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("OPENFIC_E2E_BACKEND_PORT", "19001")),
        log_level="warning",
    )
