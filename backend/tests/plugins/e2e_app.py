"""Dedicated E2E app with deterministic external providers; never production.

Run with OPENFIC_DATA_DIR pointing at a disposable directory:
  uvicorn tests.plugins.e2e_app:app --host 127.0.0.1 --port 8011
"""

import json
import re
import time
import uuid

import httpx
from fastapi import Request
from fastapi.responses import StreamingResponse
from starlette.routing import Mount

from app.main import fastapi_app
from app.main import app as app
from tests.plugins.fake_drive import FakeDrive

drive = FakeDrive()
fastapi_app.state.plugin_host.http_transport = httpx.MockTransport(drive)
requests = []


@fastapi_app.get("/_e2e/drive")
async def drive_state():
    return {"files": list(drive.files.values()), "requests": drive.requests}


@fastapi_app.post("/_e2e/drive/change")
async def change_drive(request: Request):
    body = await request.json()
    drive.change(body["id"], body["content"])
    return {"ok": True}


@fastapi_app.get("/_e2e/model-requests")
async def model_requests():
    return requests[-100:]


@fastapi_app.get("/_e2e/provider/v1/models")
async def models():
    return {
        "object": "list",
        "data": [{"id": "sdk-test-model", "object": "model", "owned_by": "e2e"}],
    }


@fastapi_app.post("/_e2e/provider/v1/chat/completions")
async def completion(request: Request):
    body = await request.json()
    requests.append(body)
    system = "\n".join(
        str(m.get("content", ""))
        for m in body.get("messages", [])
        if m.get("role") == "system"
    )
    tools = [tool["function"]["name"] for tool in body.get("tools", [])]
    content = "模型回答：验证完成。"
    tool = None
    args = {}
    official_request = next(
        (
            match
            for message in body.get("messages", [])
            if message.get("role") == "user"
            if (
                match := re.search(
                    r"官方Mod兼容验证: (\{[^\n]+\})", str(message.get("content", ""))
                )
            )
        ),
        None,
    )
    if official_request:
        target = json.loads(official_request[1])
        completed = {
            message.get("name")
            for message in body.get("messages", [])
            if message.get("role") == "tool"
        }
        # Some providers omit ToolMessage.name; the paired AI call remains canonical.
        completed.update(
            call.get("function", {}).get("name")
            for message in body.get("messages", [])
            if message.get("role") == "assistant"
            for call in message.get("tool_calls", [])
        )
        if "write_chapter" not in completed:
            tool, args = (
                "write_chapter",
                {
                    "volume_ref": {"type": "title", "value": target["volumeTitle"]},
                    "title": "官方Mod新章节",
                    "content": "新建章节的第一行。\n新建章节的第二行。",
                },
            )
        elif "edit_chapter" not in completed:
            tool, args = (
                "edit_chapter",
                {
                    "volume_ref": {"type": "title", "value": target["volumeTitle"]},
                    "chapter_ref": {"type": "title", "value": target["chapterTitle"]},
                    "old_content": "原来的句子",
                    "new_content": "修改后的句子",
                },
            )
        content = "官方 Mod 验证完成：已创建章节并修改已有章节。"
    elif "planner in a handoff" in system:
        tool = "handoff_to_writer"
        args = {"reason": "规划完成，交接写作"}
    elif "writer in a handoff" in system:
        tool = "handoff_to_reviewer"
        args = {"reason": "草稿完成，交接审稿"}
    elif "reviewer in a handoff" in system:
        content = "真实模型路径审核通过：旅人在山谷重逢旧友。"
    elif any(
        "插件同步验证" in str(m.get("content", "")) for m in body.get("messages", [])
    ):
        if not any(m.get("role") == "tool" for m in body.get("messages", [])):
            tool = next((t for t in tools if t.endswith("sync_chapters")), None)
        content = "Agent 已手动触发云同步并收到结果。"
    if tool and tool not in tools:
        tool = None
    call_id = "call_" + uuid.uuid4().hex
    usage = {
        "prompt_tokens": 16000 if official_request else 100,
        "completion_tokens": 20,
        "total_tokens": 16020 if official_request else 120,
    }
    if not body.get("stream"):
        message = {"role": "assistant", "content": content}
        if tool:
            message["tool_calls"] = [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": tool, "arguments": json.dumps(args)},
                }
            ]
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "sdk-test-model",
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": "tool_calls" if tool else "stop",
                }
            ],
            "usage": usage,
        }

    async def stream():
        base = {
            "id": "chatcmpl-test",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "sdk-test-model",
        }
        delta = {"role": "assistant", "content": content}
        if tool:
            delta["tool_calls"] = [
                {
                    "index": 0,
                    "id": call_id,
                    "type": "function",
                    "function": {"name": tool, "arguments": json.dumps(args)},
                }
            ]
        yield (
            "data: "
            + json.dumps(
                {
                    **base,
                    "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
                },
                ensure_ascii=False,
            )
            + "\n\n"
        )
        yield (
            "data: "
            + json.dumps(
                {
                    **base,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "tool_calls" if tool else "stop",
                        }
                    ],
                    "usage": usage,
                }
            )
            + "\n\n"
        )
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# The packaged app may already have its SPA fallback mounted. Test-provider
# routes must precede it, just like the production API routes do.
fastapi_app.router.routes.sort(
    key=lambda route: isinstance(route, Mount) and route.path == ""
)
