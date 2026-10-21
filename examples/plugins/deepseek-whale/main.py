"""Native OpenFic port of the DeepSeek whale concept; uses only public plugin APIs.

No DSH route, credential store, DOM injection, or compatibility runtime is used.
Account balance observations and OpenFic's USD usage estimates stay separate.
"""

import asyncio
import copy
import hashlib
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

LOCK = asyncio.Lock()
BEIJING = timezone(timedelta(hours=8))
STATE_KEY = "whale.state.v1"
DEFAULTS = {
    "size": 170,
    "visible": True,
    "bubble": True,
    "position": None,
    "phrases": [
        "今天也要写出好故事！",
        "小鲸鱼帮你看着余额。",
        "休息一下，再继续创作吧。",
    ],
    "phraseIndex": 0,
    "days": {},
    "usage": [],
    "pending": {},
    "seen": [],
    "lastTurn": None,
    "balance": None,
    "error": "请在插件配置中填写 DeepSeek API Key。",
}
CSS = """
.whale-art { display:block; width:100%; height:auto; min-height:0; border:0; padding:0; background:transparent; cursor:pointer; }
.whale-art:active { transform:scale(.96); }
.whale-art img { display:block; width:100%; height:auto; }
.whale-bubble { padding:12px; border:1px solid var(--gray-a5); border-radius:18px 18px 4px 18px; background:var(--color-panel-solid); box-shadow:0 4px 20px var(--black-a3); overflow-wrap:anywhere; }
.whale-controls { display:flex; gap:5px; justify-content:center; padding:4px; }
.whale-settings { max-width:900px; margin:auto; }
.whale-note { color:var(--gray-11); }
"""


def money(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or abs(number) > Decimal("1000000000"):
            raise ValueError("金额超出有效范围")
        return number.quantize(Decimal("0.00000001"))
    except (InvalidOperation, TypeError):
        raise ValueError("金额格式无效") from None


def day(now=None):
    return (
        datetime.fromtimestamp(time.time() if now is None else now, BEIJING)
        .date()
        .isoformat()
    )


async def state(ctx):
    value = {**copy.deepcopy(DEFAULTS), **await ctx.storage.get(STATE_KEY, {})}
    key = str(ctx.settings.get("apiKey") or "").strip()
    if value["balance"] and value["balance"]["account"] != identity(key):
        value["balance"] = None
        value["error"] = "账户已变更，请刷新余额。"
    elif not value["balance"] and key and value["error"] == DEFAULTS["error"]:
        value["error"] = "尚未刷新余额，请点击刷新。"
    return value


async def save(ctx, value):
    await ctx.storage.set(STATE_KEY, value)
    ctx.invalidate_ui()


def identity(key):
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def day_key(balance, date=None):
    return f"{balance['account']}|{balance['currency']}|{date or day()}"


def observe_balance(value, balance, now=None):
    """Decreases are observations; increases are credits, never negative spending."""
    date = day(now)
    key = day_key(balance, date)
    row = value["days"].setdefault(
        key,
        {
            "date": date,
            "currency": balance["currency"],
            "account": balance["account"],
            "opening": balance["total"],
            "last": balance["total"],
            "observed": 0,
            "credits": 0,
            "correction": 0,
            "firstAt": now or time.time(),
        },
    )
    delta = money(row["last"]) - money(balance["total"])
    if delta > 0:
        row["observed"] = float(money(row["observed"]) + delta)
    elif delta < 0:
        row["credits"] = float(money(row["credits"]) - delta)
    row["last"] = balance["total"]
    row["updatedAt"] = now or time.time()
    # Bound the ledger independently of upstream's host filesystem conventions.
    cutoff = (datetime.now(BEIJING).date() - timedelta(days=365)).isoformat()
    value["days"] = {k: v for k, v in value["days"].items() if v["date"] >= cutoff}


def spending(value, balance):
    row = value["days"].get(day_key(balance), {})
    return float(
        max(Decimal(0), money(row.get("observed", 0)) + money(row.get("correction", 0)))
    )


async def refresh(ctx, params=None):
    key = str(ctx.settings.get("apiKey") or "").strip()
    account = identity(key) if key else None
    async with LOCK:
        current = await state(ctx)
        cached = current.get("balance")
        if cached and cached["account"] != account:
            current["balance"] = None
        if not key:
            current["error"] = "请在插件配置中填写 DeepSeek API Key。"
            await save(ctx, current)
            return {"ok": False, "error": current["error"]}
    # Never hold the accounting lock during network I/O.
    failure = None
    try:
        response = await ctx.http.request(
            "GET",
            "https://api.deepseek.com/user/balance",
            headers={"Authorization": f"Bearer {key}"},
        )
        if not response["ok"]:
            failure = (
                "DeepSeek 认证失败，请检查 API Key。"
                if response["status"] in {401, 403}
                else "DeepSeek 余额服务暂时不可用。"
            )
        else:
            rows = (response["json"] or {}).get("balance_infos", [])
            info = next(
                (r for r in rows if r.get("currency") == "CNY"),
                rows[0] if rows else None,
            )
            if not info or not isinstance(info.get("currency"), str):
                raise ValueError("missing balance")
            balance = {
                "account": account,
                "currency": info["currency"][:12],
                "total": float(money(info["total_balance"])),
                "bonus": float(money(info["granted_balance"]))
                if info.get("granted_balance") is not None
                else None,
                "recharge": float(money(info["topped_up_balance"]))
                if info.get("topped_up_balance") is not None
                else None,
                "updatedAt": time.time(),
                "stale": False,
            }
    except Exception:
        # Provider error bodies/URLs may contain private data. Do not echo them.
        failure = "余额刷新失败，请稍后重试。"
    async with LOCK:
        value = await state(ctx)
        previous = value.get("balance")
        if previous and previous["account"] != account:
            value["balance"] = None
        if failure:
            value["error"] = failure
            if value["balance"]:
                value["balance"]["stale"] = True
        else:
            observe_balance(value, balance)
            value["balance"], value["error"] = balance, ""
        await save(ctx, value)
        return {"ok": failure is None, "error": failure}


async def usage_recorded(ctx, event, next_handler):
    async with LOCK:
        value = await state(ctx)
        event_id = event.get("event_id")
        if not event_id or event_id in value["seen"] or event.get("currency") != "USD":
            return await next_handler(event)
        value["seen"] = [*value["seen"], event_id][-5000:]
        cost = money(event.get("cost", 0))
        if cost < 0:
            return await next_handler(event)
        record = {
            "id": event_id,
            "date": day(),
            "cost": float(cost),
            "currency": "USD",
            "model": str(event.get("model_id") or "未提供模型名称"),
            "tokens": int(event.get("token_input", 0))
            + int(event.get("token_output", 0)),
            "session": event.get("parent_session_id") or event.get("session_id"),
            "task": event.get("task_id"),
            "revision": event.get("revision_id"),
            "at": event.get("created_at"),
            "subagent": event.get("is_subagent", False),
            "kind": event.get("usage_kind", "model"),
        }
        value["usage"] = [*value["usage"], record][-3000:]
        session = record["session"]
        bucket = f"{session}|{record['revision'] or record['task'] or 'unknown'}"
        if session:
            pending = value["pending"].setdefault(bucket, {"cost": 0, "tokens": 0})
            pending["cost"] = float(money(pending["cost"]) + cost)
            pending["tokens"] += record["tokens"]
        value["pending"] = dict(list(value["pending"].items())[-100:])
        await save(ctx, value)
    return await next_handler(event)


async def turn_settled(ctx, event, next_handler):
    async with LOCK:
        value = await state(ctx)
        bucket = f"{event.get('session_id')}|{event.get('revision_id') or event.get('task_id') or 'unknown'}"
        pending = value["pending"].pop(bucket, None)
        if pending:
            value["lastTurn"] = {
                **pending,
                "currency": "USD",
                "at": event.get("created_at"),
                "session": event["session_id"],
            }
            value["bubble"] = True
            await save(ctx, value)
    return await next_handler(event)


def node(kind, children=None, **props):
    return {"type": kind, "props": props, "children": children}


def text(value, **props):
    return node("Text", str(value), **props)


def button(label, action, **props):
    return node("Button", label, onPress=action, **props)


def icon_button(label, icon, action):
    return node(
        "IconButton",
        node("Icon", name=icon, size=16),
        label=label,
        variant="soft",
        onPress=action,
        size="1",
    )


def amount(number, currency):
    return f"{currency} {number:.2f}"


def notifications(ctx, value, balance):
    warnings = []
    if balance and balance["total"] <= ctx.settings.get("lowBalance", 5):
        warnings.append("余额偏低，请留意充值。")
    budget = ctx.settings.get("budget", 0)
    if balance and budget and spending(value, balance) >= budget:
        warnings.append("今日观测消费已达到预算。")
    return warnings


async def ui_render(ctx, params):
    value = await state(ctx)
    balance = value["balance"]
    currency = balance["currency"] if balance else ""
    if params.get("viewId") == "widget":
        if not value["visible"]:
            return {"tree": None}
        phrase = (
            value["phrases"][value["phraseIndex"] % len(value["phrases"])]
            if value["phrases"]
            else "继续创作吧！"
        )
        bubble = []
        if value["bubble"]:
            bubble = [
                node(
                    "Box",
                    [
                        text(phrase, size="2"),
                        text(
                            "余额 " + amount(balance["total"], currency)
                            if balance
                            else "余额待配置",
                            weight="bold",
                            id="whale-balance",
                        ),
                        text(
                            "今日观测 " + amount(spending(value, balance), currency)
                            if balance
                            else "在设置页配置 API Key 后刷新。",
                            size="1",
                        ),
                        text(
                            f"上一轮 USD {value['lastTurn']['cost']:.8f}"
                            if value["lastTurn"]
                            else "尚未观测到已完成回合。",
                            size="1",
                            id="whale-turn",
                        ),
                        *[
                            text(warning, size="1", color="red")
                            for warning in notifications(ctx, value, balance)
                        ],
                        text("余额已过期，显示最近成功值。", size="1", color="orange")
                        if balance and balance["stale"]
                        else None,
                    ],
                    className="whale-bubble",
                    gap=1,
                )
            ]
        content = node(
            "FloatingPanel",
            [
                *bubble,
                node(
                    "Button",
                    node(
                        "Image",
                        asset="assets/whale.png",
                        alt="DeepSeek 小鲸鱼",
                        width=value["size"],
                        fit="contain",
                    ),
                    className="whale-art",
                    label="戳一下小鲸鱼",
                    onPress="pet",
                ),
                node(
                    "Flex",
                    [
                        icon_button("刷新余额", "RefreshCw", "refresh"),
                        icon_button("小鲸鱼设置", "Settings", "settings"),
                        icon_button("收起气泡", "MessageCircle", "bubble"),
                        icon_button("隐藏挂件", "EyeOff", "hide"),
                    ],
                    className="whale-controls",
                ),
            ],
            width=value["size"] + 24,
            position=value["position"],
            dragLabel="移动小鲸鱼",
            onPositionChange="position",
        )
        return {"css": CSS, "tree": content}
    usage_today = [r for r in value["usage"] if r["date"] == day()]
    usage_cost = sum((money(r["cost"]) for r in usage_today), Decimal(0))
    recent_rows = [
        node(
            "Table.Row",
            [
                node("Table.Cell", r["date"]),
                node("Table.Cell", r["model"]),
                node("Table.Cell", str(r["tokens"])),
                node("Table.Cell", f"USD {r['cost']:.8f}"),
            ],
        )
        for r in reversed(value["usage"][-50:])
    ]
    account_rows = [
        r
        for r in value["days"].values()
        if balance and r["account"] == balance["account"]
    ]
    return {
        "css": CSS,
        "tree": node(
            "Box",
            [
                node("Heading", "DeepSeek 小鲸鱼", size="6"),
                text(
                    "按 DeepSeek Balance Whale Widget 的交互概念原生移植。账本从安装启用后开始观测。",
                    className="whale-note",
                ),
                text(value["error"], color="red", id="whale-error")
                if value["error"]
                else None,
                node(
                    "Grid",
                    [
                        node(
                            "Card",
                            [
                                text("账户余额", **{"as": "p"}),
                                text(
                                    amount(balance["total"], currency)
                                    if balance
                                    else "—",
                                    size="5",
                                    weight="bold",
                                    id="balance",
                                ),
                            ],
                        ),
                        node(
                            "Card",
                            [
                                text("今日余额观测消费", **{"as": "p"}),
                                text(
                                    amount(spending(value, balance), currency)
                                    if balance
                                    else "—",
                                    size="5",
                                    id="observed",
                                ),
                            ],
                        ),
                        node(
                            "Card",
                            [
                                text("今日 OpenFic 模型费用估算", **{"as": "p"}),
                                text(
                                    f"USD {usage_cost:.8f}", size="5", id="model-cost"
                                ),
                            ],
                        ),
                    ],
                    columns={"initial": "1", "sm": "3"},
                    gap="3",
                ),
                text(
                    "余额下降按观测累计，充值和赠金增加单独记录。可能包含赠金过期等非调用扣减，不能当作完整账单；未观测时段不补算。模型费用使用 OpenFic 配置的美元价格，两种币种不合并。",
                    size="2",
                    className="whale-note",
                ),
                text(
                    "最近成功刷新："
                    + datetime.fromtimestamp(balance["updatedAt"], BEIJING).strftime(
                        "%m-%d %H:%M:%S"
                    )
                    + ("（过期）" if balance["stale"] else "")
                    if balance
                    else "尚未成功获取余额。",
                    size="2",
                    id="refreshed",
                ),
                node(
                    "Flex",
                    [
                        button("立即刷新余额", "refresh"),
                        button(
                            "显示挂件" if not value["visible"] else "隐藏挂件",
                            "toggle-visible",
                            variant="soft",
                        ),
                        button("重置位置", "reset-position", variant="soft"),
                    ],
                    gap="3",
                    wrap="wrap",
                ),
                *[
                    text(warning, color="red", role="status")
                    for warning in notifications(ctx, value, balance)
                ],
                node("Heading", "外观与气泡", size="3"),
                text("角色大小"),
                node(
                    "Slider",
                    label="角色大小",
                    min=96,
                    max=260,
                    step=2,
                    value=[value["size"]],
                    onValueCommit="size",
                ),
                node(
                    "TextArea",
                    label="气泡台词（每行一句）",
                    value="\n".join(value["phrases"]),
                    rows=3,
                    onChange="phrases",
                ),
                node("Heading", "校正今日观测消费", size="3"),
                text(
                    "以当前账户币种填写确认后的今日消费；保存前重新获取余额。后续新观测继续累计。",
                    size="2",
                ),
                node(
                    "Input",
                    label="今日消费校正值",
                    value=value.get("correctionDraft", ""),
                    onInput="correction-draft",
                ),
                button("保存今日校正", "correct", disabled=not balance),
                text(value.get("status", ""), role="status", id="status"),
                node("Heading", "余额观测历史", size="3"),
                node(
                    "Table.Root",
                    node(
                        "Table.Body",
                        [
                            node(
                                "Table.Row",
                                [
                                    node("Table.Cell", r["date"]),
                                    node(
                                        "Table.Cell",
                                        f"{r['currency']} 观测 {r['observed']:.8f}",
                                    ),
                                    node(
                                        "Table.Cell",
                                        f"增加 {r['credits']:.8f} / 校正 {r['correction']:.8f}",
                                    ),
                                ],
                            )
                            for r in sorted(
                                account_rows, key=lambda r: r["date"], reverse=True
                            )[:30]
                        ],
                    ),
                ),
                node("Heading", "最近模型用量（USD）", size="3"),
                node("Table.Root", node("Table.Body", recent_rows)),
                text(
                    "API Key、低余额阈值和日预算在插件管理的配置中设置；密钥不回传到本界面。",
                    size="2",
                ),
            ],
            className="whale-settings",
            gap=3,
        ),
    }


async def ui_action(ctx, params):
    action = params["id"]
    if action == "settings":
        return {
            "effects": [
                {
                    "method": "ui.navigate",
                    "params": {"path": "/extensions/deepseek-whale/settings"},
                }
            ]
        }
    if action == "refresh":
        return await refresh(ctx)
    if action == "correct":
        result = await refresh(ctx)
        if not result["ok"]:
            raise ValueError("余额未能刷新，未保存校正。")
    async with LOCK:
        value = await state(ctx)
        data = params.get("value")
        if action == "position":
            if (
                not isinstance(data, dict)
                or set(data) != {"x", "y"}
                or any(
                    type(v) not in (float, int) or abs(v) > 100000
                    for v in data.values()
                )
            ):
                raise ValueError("位置无效")
            value["position"] = data
        elif action == "size":
            if (
                not isinstance(data, list)
                or len(data) != 1
                or type(data[0]) not in (int, float)
            ):
                raise ValueError("大小无效")
            value["size"] = int(max(96, min(260, data[0])))
        elif action == "phrases":
            if not isinstance(data, str) or len(data) > 4000:
                raise ValueError("台词过长")
            value["phrases"] = [
                line[:160] for line in data.splitlines() if line.strip()
            ][:30]
        elif action == "pet":
            value["phraseIndex"] += 1
            value["bubble"] = True
        elif action == "bubble":
            value["bubble"] = not value["bubble"]
        elif action == "hide":
            value["visible"] = False
        elif action == "toggle-visible":
            value["visible"] = not value["visible"]
        elif action == "reset-position":
            value["position"] = None
        elif action == "correction-draft":
            value["correctionDraft"] = str(data)[:40]
        elif action == "correct":
            requested = money(value.get("correctionDraft", ""))
            if requested < 0:
                raise ValueError("今日消费不能为负数")
            row = value["days"][day_key(value["balance"])]
            row["correction"] = float(requested - money(row["observed"]))
            value["status"] = "今日校正已保存"
        else:
            raise ValueError("未知操作")
        await save(ctx, value)


def register(host):
    host.register_command("ui.render", ui_render)
    host.register_command("ui.action", ui_action)
    host.register_command("balance.refresh", refresh)
    host.register_interval(60, refresh)
    host.register_hook("usage.recorded", usage_recorded)
    host.register_hook("turn.settled", turn_settled)
