"""Deterministic OpenAI wire provider for the pre-existing Agent browser tests.

Only this external dependency is simulated. Tools, approval, queue, cancellation,
compaction, persistence and frontend all execute the actual application paths.
"""

import asyncio
import json
import re
import time
import uuid

from fastapi import Request
from fastapi.responses import StreamingResponse


async def completion(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    users = [str(m.get("content", "")) for m in messages if m.get("role") == "user"]
    prompt = users[-1] if users else ""
    available = {t["function"]["name"] for t in body.get("tools", [])}
    calls = []
    previous_calls = [
        c
        for m in messages
        if m.get("role") == "assistant"
        for c in m.get("tool_calls", [])
    ]
    last_user = max(
        (i for i, m in enumerate(messages) if m.get("role") == "user"), default=-1
    )
    since_user = [
        c
        for m in messages[last_user + 1 :]
        if m.get("role") == "assistant"
        for c in m.get("tool_calls", [])
    ]
    quotes = re.findall(r"「([^」]+)」", prompt)
    content = quotes[-1] if quotes else "模型回答：验证完成。"
    delay = 1.5
    if (
        any(marker in prompt for marker in ("复活测试", "取消测试", "排队测试"))
        and not since_user
    ):
        # Keep the model in flight while original tests read task metadata,
        # click Stop or enqueue a message; do not race an approval panel.
        delay = 10
    if "ask_user" in prompt and "ask_user" in available and not since_user:
        calls = [
            (
                "ask_user",
                {
                    "questions": [
                        {
                            "title": "请选择写作偏好",
                            "description": "用于回归验证",
                            "options": [
                                {"label": "冒险", "description": "冒险故事"},
                                {"label": "日常", "description": "日常故事"},
                            ],
                        }
                    ]
                },
            )
        ]
    elif "创建一个名为" in prompt and "write_chapter" in available and not since_user:
        calls = [
            (
                "write_chapter",
                {
                    "volume_ref": {"type": "title", "value": "第一卷"},
                    "title": quotes[0],
                    "content": "旅人走进山谷，溪水沿着石阶流向远方。" * 4,
                },
            )
        ]
    elif (
        "前 15 章" in prompt
        and "read_chapter" in available
        and not any(c["function"]["name"] == "read_chapter" for c in previous_calls)
    ):
        calls = [
            (
                "read_chapter",
                {
                    "volume_ref": {"type": "title", "value": "第一卷"},
                    "chapter_ref": {"type": "title", "value": f"回归章节{i}"},
                },
            )
            for i in range(1, 16)
        ]
        content = "阅读完成"
    elif "总结完成" in prompt:
        content = "旅人沿着山谷前行，整体基调宁静而充满希望。总结完成"
    if not available:
        # Compaction requests must stay pending long enough to verify cancellation.
        delay = 5
        content = "已保留用户目标、章节事实、工具调用结果和待办事项的会话摘要。" * 6
    tool_calls = [
        {
            "id": "call_" + uuid.uuid4().hex,
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps(args, ensure_ascii=False),
            },
        }
        for name, args in calls
    ]
    tokens = min(26000, max(100, sum(len(str(m.get("content", ""))) for m in messages)))
    usage = {
        "prompt_tokens": tokens,
        "completion_tokens": 30,
        "total_tokens": tokens + 30,
    }
    base = {
        "id": "chatcmpl-regression",
        "created": int(time.time()),
        "model": "sdk-test-model",
    }
    if not body.get("stream"):
        await asyncio.sleep(delay)
        return {
            **base,
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                        **({"tool_calls": tool_calls} if tool_calls else {}),
                    },
                    "finish_reason": "tool_calls" if calls else "stop",
                }
            ],
            "usage": usage,
        }

    async def stream():
        await asyncio.sleep(delay)
        delta = {"role": "assistant", "content": content}
        if tool_calls:
            delta["tool_calls"] = [
                {"index": index, **call} for index, call in enumerate(tool_calls)
            ]
        yield (
            "data: "
            + json.dumps(
                {
                    **base,
                    "object": "chat.completion.chunk",
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
                    "object": "chat.completion.chunk",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "tool_calls" if calls else "stop",
                        }
                    ],
                    "usage": usage,
                }
            )
            + "\n\n"
        )
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
