"""Interactive actions, independent of the view layout."""

async def action(ctx, params):
    action_id = params["id"]
    if action_id == "increment":
        await ctx.storage.set("count", await ctx.storage.get("count", 0) + 1)
    elif action_id == "position":
        await ctx.storage.set("position", params["value"])
    elif action_id == "permission":
        # Deliberately absent projects.read; Inspector must show the actual denial.
        await ctx.call("api.request", {"method": "GET", "path": "/projects"})
    elif action_id == "css-warning":
        await ctx.storage.set("css-warning", True)
    elif action_id == "secret":
        await ctx.secrets.set("demo", ctx.settings.get("apiKey", ""))
        # The value never appears in the UI. Both backend and frontend traces must
        # redact it even under this arbitrary, non-sensitive dictionary key.
        return {"message": ctx.settings.get("apiKey", "")}
    else:
        raise ValueError("Unknown action")
    ctx.invalidate_ui()
