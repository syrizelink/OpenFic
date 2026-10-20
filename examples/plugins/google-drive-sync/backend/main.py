"""Google Drive chapter sync via public SDK only. No application internals."""

import asyncio
import hashlib
import json
import time
import uuid
from urllib.parse import quote, urlencode


def digest(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def connect(ctx, params):
    client_id = ctx.settings["clientId"]
    if not client_id:
        raise ValueError("请先在插件配置中填写 Google OAuth Client ID")
    return await ctx.oauth.start(
        authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=ctx.settings["clientSecret"],
        scopes=["https://www.googleapis.com/auth/drive.file"],
        extra={"access_type": "offline", "prompt": "consent"},
    )


async def token(ctx, refresh=False):
    tokens = await ctx.secrets.get("oauth.tokens")
    if not tokens:
        raise ValueError("请先连接 Google Drive，或导入已有的 OAuth 令牌")
    if (
        refresh
        or time.time()
        > tokens.get("obtained_at", 0) + tokens.get("expires_in", 3600) - 60
    ):
        if not tokens.get("refresh_token"):
            if refresh:
                raise ValueError("Google Drive 授权已过期，请重新连接")
            return tokens["access_token"]
        response = await ctx.http.request(
            "POST",
            "https://oauth2.googleapis.com/token",
            form={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": ctx.settings["clientId"],
                "client_secret": ctx.settings["clientSecret"],
            },
        )
        if not response["ok"] or not response["json"].get("access_token"):
            raise ValueError("Google Drive 刷新授权失败，请重新连接")
        tokens = {**tokens, **response["json"], "obtained_at": time.time()}
        await ctx.secrets.set("oauth.tokens", tokens)
    return tokens["access_token"]


async def request(ctx, method, url, **options):
    base_headers = options.pop("headers", {})
    refresh = False
    for attempt in range(3):
        headers = {
            **base_headers,
            "Authorization": "Bearer " + await token(ctx, refresh=refresh),
        }
        result = await ctx.http.request(method, url, headers=headers, **options)
        if result["status"] not in {401, 429, 500, 502, 503, 504}:
            break
        refresh = result["status"] == 401
        await asyncio.sleep(0.2 * (2**attempt))
    if not result["ok"]:
        if result["status"] == 412:
            raise ValueError("云端文件在同步中再次变化，请刷新后解决冲突")
        raise ValueError(
            f"Google Drive 请求失败（HTTP {result['status']}），本地内容未被覆盖"
        )
    return result


async def status(ctx, params):
    project_id = params.get("projectId")
    return {
        "connected": bool(await ctx.secrets.get("oauth.tokens")),
        "lastRun": await ctx.storage.get("sync:" + project_id) if project_id else None,
    }


async def disconnect(ctx, params):
    await ctx.secrets.delete("oauth.tokens")
    return {"connected": False}


async def upload(ctx, project_id, chapter, file_id=None, etag=None):
    boundary = "openfic-" + uuid.uuid4().hex
    payload = {
        "schema": "openfic.chapter.v1",
        "projectId": project_id,
        "chapterId": chapter["id"],
        "title": chapter["title"],
        "content": chapter["content"],
        "word_count": chapter["word_count"],
        "volumeId": chapter["volume_id"],
        "order": chapter["order"],
    }
    metadata = {
        "name": chapter["title"] + ".openfic.json",
        "mimeType": "application/json",
        "appProperties": {
            "openficProjectId": project_id,
            "openficChapterId": chapter["id"],
        },
    }
    if not file_id and ctx.settings["folderId"]:
        metadata["parents"] = [ctx.settings["folderId"]]
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
        + json.dumps(metadata, ensure_ascii=False)
        + f"\r\n--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
        + json.dumps(payload, ensure_ascii=False)
        + f"\r\n--{boundary}--\r\n"
    )
    headers = {"Content-Type": "multipart/related; boundary=" + boundary}
    if etag:
        headers["If-Match"] = etag
    url = (
        "https://www.googleapis.com/upload/drive/v3/files"
        + ("/" + quote(file_id, safe="") if file_id else "")
        + "?uploadType=multipart&fields=id,modifiedTime"
    )
    response = await request(
        ctx, "PATCH" if file_id else "POST", url, body=body, headers=headers
    )
    return response["json"]["id"]


async def sync(ctx, params):
    project_id = params.get("projectId") or ctx.runtime.get("project_id")
    if not project_id:
        raise ValueError("请选择项目")
    mode = params.get("mode", "two-way")
    if mode not in {"push", "pull", "two-way"}:
        raise ValueError("Unknown sync mode")
    dry_run = params.get("dryRun", False)
    resolutions = params.get("resolutions", {})
    entities = await ctx.data.project_entities(project_id)
    state = await ctx.storage.get("sync:" + project_id, {"chapters": {}})
    mapping = state.setdefault("chapters", {})
    remote = []
    page_token = None
    query = f"trashed = false and appProperties has {{ key='openficProjectId' and value='{project_id}' }}"
    if ctx.settings["folderId"]:
        folder = ctx.settings["folderId"]
        if not all(c.isalnum() or c in "_-" for c in folder):
            raise ValueError("Invalid folder ID")
        query += f" and '{folder}' in parents"
    while True:
        query_params = {
            "q": query,
            "fields": "nextPageToken,files(id,name,appProperties,modifiedTime)",
            "pageSize": 1000,
        }
        if page_token:
            query_params["pageToken"] = page_token
        data = (
            await request(
                ctx,
                "GET",
                "https://www.googleapis.com/drive/v3/files?" + urlencode(query_params),
            )
        )["json"]
        remote.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        if len(remote) > 10000:
            raise ValueError("Remote listing exceeds 10000 chapters")
    by_chapter = {f.get("appProperties", {}).get("openficChapterId"): f for f in remote}
    by_file = {f["id"]: f for f in remote}
    report = {
        "projectId": project_id,
        "mode": mode,
        "dryRun": dry_run,
        "uploaded": 0,
        "downloaded": 0,
        "unchanged": 0,
        "pending": 0,
        "conflicts": [],
        "imported": 0,
        "time": time.time(),
    }
    consumed = set()
    try:
        for item in entities["chapters"]:
            chapter = await ctx.chapters.get(item["id"])
            previous = mapping.get(chapter["id"], {})
            cloud = by_file.get(previous.get("fileId")) or by_chapter.get(chapter["id"])
            local_hash = digest(chapter["content"])
            if not cloud:
                if mode == "pull":
                    report["pending"] += 1
                    continue
                if not dry_run:
                    file_id = await upload(ctx, project_id, chapter)
                    mapping[chapter["id"]] = {
                        "fileId": file_id,
                        "baseHash": local_hash,
                        "title": chapter["title"],
                    }
                report["uploaded"] += 1
                continue
            consumed.add(cloud["id"])
            result = await request(
                ctx,
                "GET",
                f"https://www.googleapis.com/drive/v3/files/{quote(cloud['id'], safe='')}?alt=media",
            )
            payload = result["json"]
            if (
                not isinstance(payload, dict)
                or payload.get("schema") != "openfic.chapter.v1"
                or payload.get("projectId") != project_id
                or not isinstance(payload.get("content"), str)
            ):
                raise ValueError("云端文件格式或项目身份不匹配")
            remote_hash = digest(payload["content"])
            same = local_hash == remote_hash and chapter["title"] == payload.get(
                "title"
            )
            local_changed = local_hash != previous.get("baseHash") or chapter[
                "title"
            ] != previous.get("title", chapter["title"])
            remote_changed = remote_hash != previous.get("baseHash") or payload.get(
                "title"
            ) != previous.get("title", payload.get("title"))
            resolution = resolutions.get(chapter["id"])
            if same:
                report["unchanged"] += 1
            elif (
                local_changed
                and remote_changed
                and resolution not in {"local", "remote"}
            ):
                report["conflicts"].append(
                    {
                        "chapterId": chapter["id"],
                        "title": chapter["title"],
                        "fileId": cloud["id"],
                    }
                )
                continue
            elif resolution == "local" or (
                local_changed and mode != "pull" and resolution != "remote"
            ):
                if not dry_run:
                    await upload(
                        ctx,
                        project_id,
                        chapter,
                        cloud["id"],
                        result["headers"].get("etag"),
                    )
                remote_hash = local_hash
                report["uploaded"] += 1
            elif resolution == "remote" or (remote_changed and mode != "push"):
                if not dry_run:
                    await ctx.chapters.update(
                        chapter["id"],
                        {
                            "title": payload["title"],
                            "content": payload["content"],
                            "word_count": payload.get("word_count"),
                        },
                    )
                local_hash = remote_hash
                chapter["title"] = payload["title"]
                report["downloaded"] += 1
            else:
                report["pending"] += 1
                continue
            if not dry_run:
                mapping[chapter["id"]] = {
                    "fileId": cloud["id"],
                    "baseHash": local_hash,
                    "title": chapter["title"],
                }
        if mode != "push":
            for cloud in remote:
                if cloud["id"] in consumed:
                    continue
                payload = (
                    await request(
                        ctx,
                        "GET",
                        f"https://www.googleapis.com/drive/v3/files/{quote(cloud['id'], safe='')}?alt=media",
                    )
                )["json"]
                if (
                    payload.get("schema") != "openfic.chapter.v1"
                    or payload.get("projectId") != project_id
                ):
                    continue
                if not dry_run:
                    chapter = await ctx.chapters.create(
                        {
                            "volume_id": entities["volumes"][0]["id"],
                            "title": payload["title"],
                            "content": payload["content"],
                            "word_count": payload.get("word_count"),
                        },
                        project_id,
                    )
                    mapping[chapter["id"]] = {
                        "fileId": cloud["id"],
                        "baseHash": digest(payload["content"]),
                        "title": chapter["title"],
                    }
                report["imported"] += 1
    finally:
        if not dry_run:
            state["lastReport"] = report
            await ctx.storage.set("sync:" + project_id, state)
    ctx.emit("sync.completed", report)
    return report


async def agent_sync(ctx, params):
    # A backup tool must not silently change the active Agent revision through
    # user-edit APIs. Downloads and conflict resolution stay in the plugin UI.
    return await sync(ctx, {**params, "mode": "push"})


def ui_node(kind, children=None, **props):
    node = {"type": kind, "props": props, "children": children}
    if kind in {"Input", "TextArea"} and props.get("label"):
        return {
            "type": "Flex",
            "props": {"direction": "column", "gap": "2", "minWidth": "0"},
            "children": [
                {
                    "type": "Text",
                    "props": {"size": "2", "weight": "medium"},
                    "children": props["label"],
                },
                node,
            ],
        }
    return node


UI_CSS = """
:scope { --example-accent: var(--accent-9); }
.example-page { width: 100%; max-width: 1100px; margin: 0 auto; min-width: 0; }
.example-panel { padding: 20px; min-width: 0; }
.example-title { color: var(--accent-11); }
.example-actions { flex-wrap: wrap; }
.example-output { display: block; white-space: pre-wrap; overflow-wrap: anywhere; max-height: 24rem; overflow: auto; }
.example-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.example-metric strong { display: block; font-size: 26px; margin-top: 8px; }
.example-table { overflow-x: auto; }
.example-conflict { border: 1px solid var(--orange-7); padding: 12px; border-radius: 8px; }
.example-compact { padding: 8px; }
@media (max-width: 640px) {
  .example-panel { padding: 12px; }
  .example-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .example-actions > button { flex: 1 1 auto; }
}
"""


def ui_button(title, action, **props):
    return ui_node("Button", title, onPress=action, **props)


def ui_row(*children):
    return ui_node(
        "Flex", list(children), gap="3", align="center", className="example-actions"
    )


def ui_panel(*children):
    return ui_node(
        "Card",
        ui_node("Flex", list(children), direction="column", gap="4"),
        className="example-panel",
    )


def ui_status(state):
    return ui_node(
        "Text",
        state.get("status", ""),
        id="status",
        role="status",
        size="2",
        color="gray",
    )


def ui_document(*children, compact=False):
    return {
        "css": UI_CSS,
        "tree": ui_node(
            "Flex",
            list(children),
            direction="column",
            gap="4",
            **{
                "className": "example-page" + (" example-compact" if compact else ""),
            },
        ),
    }


async def ui_state(ctx, params, global_default=False):
    context = params.get("context", {})
    key = (
        "ui:"
        + params.get("viewId", "main")
        + ":"
        + str(context.get("projectId") or "global")
    )
    state = await ctx.storage.get(key, {})
    if "project" not in state:
        projects = await ctx.data.list_projects()
        state["project"] = context.get("projectId") or (
            "" if global_default or not projects else projects[0]["id"]
        )
    return key, state


async def ui_render(ctx, params):
    _, state = await ui_state(ctx, params)
    project = state["project"]
    connection = await status(ctx, {"projectId": project})
    if params.get("viewId") == "toolbar":
        return ui_document(
            ui_row(
                ui_button("保存并同步本项目", "toolbar-sync", disabled=not project),
                ui_node(
                    "Badge",
                    "已连接" if connection["connected"] else "尚未连接",
                    color="green" if connection["connected"] else "gray",
                ),
            ),
            ui_status(state),
            compact=True,
        )
    report = state.get("report") or (connection.get("lastRun") or {}).get("lastReport")
    report_nodes = []
    if report:
        report_nodes.append(
            ui_node(
                "Text",
                f"上传 {report['uploaded']} · 下载 {report['downloaded']} · 导入 {report['imported']} · 无变化 {report['unchanged']} · 待同步 {report['pending']} · 冲突 {len(report['conflicts'])}",
                id="report",
            )
        )
        conflicts = []
        for item in report["conflicts"]:
            chapter_id = item["chapterId"]
            conflicts.append(
                ui_node(
                    "Flex",
                    [
                        ui_node("Text", item["title"] + "：本地与云端均有修改"),
                        ui_row(
                            *[
                                ui_node(
                                    "AlertDialog.Root",
                                    [
                                        ui_node(
                                            "AlertDialog.Trigger",
                                            ui_button(label, "", variant="soft"),
                                        ),
                                        ui_node(
                                            "AlertDialog.Content",
                                            [
                                                ui_node(
                                                    "AlertDialog.Title",
                                                    "确认解决章节冲突",
                                                ),
                                                ui_node(
                                                    "AlertDialog.Description",
                                                    "确认以所选版本覆盖另一端的这一章？",
                                                ),
                                                ui_row(
                                                    ui_node(
                                                        "AlertDialog.Cancel",
                                                        ui_button(
                                                            "取消", "", variant="soft"
                                                        ),
                                                    ),
                                                    ui_node(
                                                        "AlertDialog.Action",
                                                        ui_button(
                                                            "确认覆盖",
                                                            "resolve:"
                                                            + side
                                                            + ":"
                                                            + chapter_id,
                                                            color="orange",
                                                        ),
                                                    ),
                                                ),
                                            ],
                                        ),
                                    ],
                                )
                                for side, label in [
                                    ("local", "使用本地版本"),
                                    ("remote", "使用云端版本"),
                                ]
                            ]
                        ),
                    ],
                    direction="column",
                    gap="3",
                    className="example-conflict",
                )
            )
        report_nodes.append(
            ui_node("Flex", conflicts, direction="column", gap="3", id="conflicts")
        )
    oauth = state.get("oauth")
    return ui_document(
        ui_node("Heading", "Google Drive 章节同步", className="example-title"),
        ui_node(
            "Text",
            "同步已保存的章节。两端同时修改时保留双方内容，待你选择解决冲突。不会传播删除。",
            color="gray",
            size="2",
        ),
        ui_panel(
            ui_row(
                ui_button("连接 Google Drive", "connect"),
                ui_button("断开连接", "disconnect", variant="soft"),
                ui_node(
                    "Badge",
                    "已连接" if connection["connected"] else "尚未连接",
                    id="connection",
                    color="green" if connection["connected"] else "gray",
                ),
            ),
            *(
                [
                    ui_node("Link", "打开 Google 授权页面", href=oauth["url"]),
                    ui_node(
                        "Text",
                        "OAuth 控制台需登记的 Redirect URI：" + oauth["redirect_uri"],
                        size="1",
                    ),
                ]
                if oauth
                else []
            ),
            ui_node("Heading", "使用已有 OAuth access token", size="3"),
            ui_node(
                "Input",
                label="Access token",
                type="password",
                value="",
                onChange="token-draft",
                autoComplete="off",
                key=str(state.get("tokenVersion", 0)),
            ),
            ui_button("安全保存令牌", "token", variant="soft"),
        ),
        ui_panel(
            ui_node(
                "ProjectSelector", label="选择项目", value=project, onChange="project"
            ),
            ui_node(
                "Select",
                label="同步方向",
                value=state.get("mode", "two-way"),
                options=[
                    {"value": "two-way", "label": "双向同步"},
                    {"value": "push", "label": "仅上传本地变化"},
                    {"value": "pull", "label": "仅拉取云端变化"},
                ],
                onChange="mode",
            ),
            ui_row(
                ui_button("立即同步", "sync", disabled=not project),
                ui_button("预览变化", "preview", variant="soft", disabled=not project),
            ),
            ui_status(state),
            *report_nodes,
        ),
    )


async def ui_action(ctx, params):
    key, state = await ui_state(ctx, params)
    action = params["id"]
    if action in {"project", "mode"}:
        state[action] = params["value"]
        state.pop("report", None)
        state["status"] = ""
    elif action == "connect":
        state["oauth"] = await connect(ctx, {})
        state["status"] = "请在授权页面完成连接，然后返回本页。"
    elif action == "disconnect":
        await disconnect(ctx, {})
        await ctx.secrets.delete("ui.token.draft")
        state.pop("oauth", None)
        state["status"] = "已断开连接"
    elif action == "token-draft":
        await ctx.secrets.set("ui.token.draft", str(params["value"]))
        return
    elif action == "token":
        value = str(await ctx.secrets.get("ui.token.draft", "")).strip()
        if not value:
            raise ValueError("请输入令牌")
        await ctx.secrets.set(
            "oauth.tokens",
            {"access_token": value, "obtained_at": time.time(), "expires_in": 3600},
        )
        await ctx.secrets.delete("ui.token.draft")
        state["tokenVersion"] = time.time()
        state["status"] = "令牌已加密保存"
    elif action == "toolbar-sync":
        return {"effects": [{"method": "editor.save"}], "next": "saved-sync"}
    elif action in {"sync", "preview", "saved-sync"} or action.startswith("resolve:"):
        resolutions = {}
        if action.startswith("resolve:"):
            _, side, chapter_id = action.split(":", 2)
            if side not in {"local", "remote"}:
                raise ValueError("Unknown resolution")
            resolutions[chapter_id] = side
        report = await sync(
            ctx,
            {
                "projectId": state["project"],
                "mode": state.get("mode", "two-way"),
                "dryRun": action == "preview",
                "resolutions": resolutions,
            },
        )
        state["report"] = report
        state["status"] = "变化预览完成，未修改内容" if report["dryRun"] else "同步完成"
    else:
        raise ValueError("Unknown UI action")
    await ctx.storage.set(key, state)
    ctx.host.emit("ui.invalidate", {}, ctx.plugin_id)


def register(host):
    host.register_command("ui.render", ui_render)
    host.register_command("ui.action", ui_action)
    host.register_command("drive.connect", connect)
    host.register_command("drive.status", status)
    host.register_command("drive.disconnect", disconnect)
    host.register_command("drive.sync", sync)
    host.register_tool(
        "sync_chapters",
        "Upload this project’s saved chapters to Google Drive. Conflicts are reported without overwriting. Downloads and two-way conflict resolution are available in the plugin UI. Requires a connected Drive account.",
        {
            "type": "object",
            "properties": {
                "projectId": {"type": "string"},
            },
        },
        agent_sync,
    )
