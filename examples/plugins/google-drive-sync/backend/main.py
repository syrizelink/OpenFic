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


def register(host):
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
