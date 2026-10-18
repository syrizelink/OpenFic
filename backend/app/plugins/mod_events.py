"""Translate host data into Claude-shaped events without exposing host files."""

from urllib.parse import quote

from pydantic_core import to_jsonable_python
from sqlalchemy import select
from sqlmodel import col


def tool_event(data, runtime):
    arguments = data.get("input")
    if not isinstance(arguments, dict):
        return data, lambda event: event
    wire_arguments = to_jsonable_python(arguments)
    translated = {**wire_arguments, **to_jsonable_python(data)}
    name = data.get("tool", "")
    mapping = {key: key for key in arguments}
    root = "openfic://projects/" + quote(str(runtime.get("project_id") or ""), safe="")
    if name in {"write_chapter", "write_note"}:
        kind = "chapters" if name == "write_chapter" else "notes"
        translated.update(
            tool="Write",
            file_path=f"{root}/{kind}/{arguments.get('title', 'untitled')}",
        )
    elif (
        name in {"edit_chapter", "edit_note"}
        and isinstance(arguments.get("old_content"), str)
        and isinstance(arguments.get("new_content"), str)
    ):
        kind = "chapters" if name == "edit_chapter" else "notes"
        ref = (
            wire_arguments.get("chapter_ref" if kind == "chapters" else "note_ref")
            or {}
        )
        translated.update(
            tool="Edit",
            file_path=f"{root}/{kind}/{ref.get('value', 'unknown')}",
            old_string=arguments["old_content"],
            new_string=arguments["new_content"],
        )
        mapping.update(old_content="old_string", new_content="new_string")

    def restore(event):
        if not isinstance(event, dict) or event.get("tool") != translated.get("tool"):
            raise ValueError("Mod middleware cannot change the tool identity")
        if event.get("file_path") != translated.get("file_path"):
            raise ValueError("Mod middleware cannot redirect a virtual document path")
        wire_input = event.get("input", wire_arguments)
        if not isinstance(wire_input, dict):
            raise ValueError("Mod tool arguments must be an object")
        restored = {
            **data,
            "input": {
                key: arguments[key]
                if key in arguments and value == wire_arguments[key]
                else value
                for key, value in wire_input.items()
            },
        }
        for native, field in mapping.items():
            if event.get(field) != translated.get(field):
                restored["input"][native] = event.get(field)
        if event.get("deny"):
            restored["deny"] = event["deny"]
        return restored

    return translated, restore


async def session_usage(context):
    context.require("sessions.read")
    from app.storage.models.task import Task

    state = context.runtime
    window = (state.get("model_config") or {}).get("max_context_tokens", 0)
    session = context.data._session
    task_id, session_id = state.get("task_id"), state.get("session_id")
    tokens = 0
    if session is not None and (task_id or session_id):
        row = (
            await session.execute(
                select(col(Task.context_input_tokens)).where(
                    col(Task.id) == task_id
                    if task_id
                    else col(Task.agent_session_id) == session_id
                )
            )
        ).first()
        if row:
            tokens = row[0]
    return {
        "context": {
            "tokens": tokens,
            "window": window,
            "percent": (tokens / window * 100) if window else 0,
        }
        if window
        else None
    }
