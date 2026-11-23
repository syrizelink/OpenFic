"""Demonstrate selection menu callbacks and quote effects."""

DEFAULT_PROMPT = "请结合上下文分析这段引用，指出值得注意的细节。"


async def selection_action(context, params):
    action_id = params.get("id")
    ui_context = params.get("context") or {}
    selected = ui_context.get("selection")

    if action_id in {"inspect-selection", "inspect-message", "inspect-contextmenu", "quote"}:
        if not isinstance(selected, dict) or params.get("value") != selected:
            raise ValueError("菜单参数中的选区快照不一致")
        return {
            "effects": [{"method": "selection.read"}],
            "next": "quote-ready" if action_id == "quote" else "inspect-ready",
        }

    if action_id not in {"inspect-ready", "quote-ready"}:
        raise ValueError("未知的选区操作")
    values = params.get("value")
    if not isinstance(values, list) or len(values) != 1 or values[0] != selected:
        raise ValueError("selection.read 返回的选区与菜单快照不一致")
    if not isinstance(selected, dict):
        raise ValueError("没有可用的选区")

    if action_id == "quote-ready":
        if not selected.get("target"):
            raise ValueError("没有明确的目标 Agent 会话，请先打开当前项目的 Agent 标签")
        prompt = context.settings.get("quotePrompt", DEFAULT_PROMPT)
        return {"effects": [
            {"method": "assistant.quote", "params": {"prompt": prompt}},
            {"method": "ui.toast", "params": {"text": "引用已添加到 Agent 输入框"}},
        ]}

    source = selected.get("source") or {}
    bounds = selected.get("bounds") or {}
    target = selected.get("target") or {}
    preview = str(selected.get("text", ""))[:80].replace("\n", " ")
    target_summary = (
        f"{target.get('projectId', '-')} / {target.get('tabId', '-')} / "
        f"{target.get('taskId') or '新会话'}"
        if target
        else "无"
    )
    summary = (
        f"来源: {source.get('kind', '-')} / {source.get('id', '-')}\n"
        f"项目: {source.get('projectId', '-')}\n"
        f"位置: x={bounds.get('x', '-')} y={bounds.get('y', '-')} "
        f"宽={bounds.get('width', '-')} 高={bounds.get('height', '-')}\n"
        f"目标: {target_summary}\n"
        f"选区: {preview}"
    )
    return {"effects": [{"method": "ui.toast", "params": {"text": summary}}]}


def register(host):
    host.register_command("selection.action", selection_action)
