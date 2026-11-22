"""DeepSeek balance observations for the iframe whale widget."""

import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation

LOCK = asyncio.Lock()
KEY = "whale.iframe.state"


def money(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or abs(result) > Decimal("1000000000"):
            raise ValueError("Invalid amount")
        return result.quantize(Decimal("0.00000001"))
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid amount") from None


def account(ctx):
    key = str(ctx.settings.get("apiKey") or "").strip()
    return key, hashlib.sha256(key.encode()).hexdigest()[:24] if key else None


def date():
    return datetime.now(timezone(timedelta(hours=8))).date().isoformat()


async def load(ctx):
    return await ctx.storage.get(
        KEY, {"days": {}, "seen": [], "pending": {}, "balance": None, "error": ""}
    )


async def snapshot(ctx, params):
    async with LOCK:
        state = await load(ctx)
        key, identity = account(ctx)
        balance = state.get("balance")
        if balance and balance["account"] != identity:
            balance = None
        day_key = f"{identity}|{balance['currency']}|{date()}" if balance else ""
        day = state.get("days", {}).get(day_key, {})
        used = float(
            max(Decimal(0), money(day.get("used", 0)) + money(day.get("correction", 0)))
        )
        return {
            "balance": balance,
            "today": used,
            "lastTurn": state.get("lastTurn"),
            "error": state.get("error")
            if key
            else "请在插件配置中填写 DeepSeek API Key。",
            "lowBalance": ctx.settings.get("lowBalance", 5),
            "budget": ctx.settings.get("budget", 0),
        }


async def refresh(ctx, params=None):
    key, identity = account(ctx)
    if not key:
        return {"ok": False}
    failure = ""
    balance = None
    try:
        response = await ctx.http.request(
            "GET",
            "https://api.deepseek.com/user/balance",
            headers={"Authorization": f"Bearer {key}"},
        )
        if not response["ok"]:
            raise ValueError("Balance request failed")
        rows = (response["json"] or {}).get("balance_infos", [])
        row = next(
            (item for item in rows if item.get("currency") == "CNY"),
            rows[0] if rows else None,
        )
        if not row or not isinstance(row.get("currency"), str):
            raise ValueError("Missing balance")
        balance = {
            "account": identity,
            "currency": row["currency"][:12],
            "total": float(money(row["total_balance"])),
            "stale": False,
        }
    except Exception:
        failure = "余额刷新失败，显示最近成功值。"
    async with LOCK:
        if account(ctx)[1] != identity:
            return {"ok": False}
        state = await load(ctx)
        if failure:
            if state.get("balance") and state["balance"]["account"] == identity:
                state["balance"]["stale"] = True
        else:
            day_key = f"{identity}|{balance['currency']}|{date()}"
            day = state.setdefault("days", {}).setdefault(
                day_key,
                {
                    "date": date(),
                    "last": balance["total"],
                    "used": 0,
                    "credits": 0,
                    "correction": 0,
                },
            )
            delta = money(day["last"]) - money(balance["total"])
            if delta > 0:
                day["used"] = float(money(day["used"]) + delta)
            else:
                day["credits"] = float(money(day["credits"]) - delta)
            day["last"] = balance["total"]
            state["balance"] = balance
            cutoff = (
                datetime.now(timezone(timedelta(hours=8))).date() - timedelta(days=365)
            ).isoformat()
            state["days"] = {
                k: v for k, v in state["days"].items() if v["date"] >= cutoff
            }
        state["error"] = failure
        await ctx.storage.set(KEY, state)
        ctx.invalidate_ui("widget")
    return {"ok": not failure}


async def correct(ctx, params):
    amount = money(params.get("amount"))
    if amount < 0:
        raise ValueError("消费不能为负数")
    if not (await refresh(ctx))["ok"]:
        raise ValueError("余额未能刷新，未保存校正。")
    async with LOCK:
        state = await load(ctx)
        balance = state["balance"]
        day = state["days"][f"{balance['account']}|{balance['currency']}|{date()}"]
        day["correction"] = float(amount - money(day["used"]))
        await ctx.storage.set(KEY, state)
        ctx.invalidate_ui("widget")


async def usage_recorded(ctx, event, next_handler):
    async with LOCK:
        state = await load(ctx)
        event_id = event.get("event_id")
        if (
            event_id
            and event_id not in state["seen"]
            and event.get("currency") == "USD"
        ):
            cost = money(event.get("cost", 0))
            if cost >= 0:
                state["seen"] = [*state["seen"], event_id][-5000:]
                session = event.get("parent_session_id") or event.get("session_id")
                if session:
                    bucket = f"{session}|{event.get('revision_id') or event.get('task_id') or 'unknown'}"
                    pending = state["pending"].setdefault(
                        bucket, {"cost": 0, "tokens": 0}
                    )
                    pending["cost"] = float(money(pending["cost"]) + cost)
                    pending["tokens"] += int(event.get("token_input", 0)) + int(
                        event.get("token_output", 0)
                    )
                    state["pending"] = dict(list(state["pending"].items())[-100:])
                await ctx.storage.set(KEY, state)
    return await next_handler(event)


async def turn_settled(ctx, event, next_handler):
    async with LOCK:
        state = await load(ctx)
        bucket = f"{event.get('session_id')}|{event.get('revision_id') or event.get('task_id') or 'unknown'}"
        pending = state["pending"].pop(bucket, None)
        if pending:
            state["lastTurn"] = {
                **pending,
                "currency": "USD",
                "id": event.get("revision_id") or event.get("task_id"),
            }
            await ctx.storage.set(KEY, state)
            ctx.invalidate_ui("widget")
    return await next_handler(event)


def register(host):
    host.register_command("whale.snapshot", snapshot)
    host.register_command("whale.refresh", refresh)
    host.register_command("whale.correct", correct)
    host.register_interval(60, refresh)
    host.register_hook("usage.recorded", usage_recorded)
    host.register_hook("turn.settled", turn_settled)
