"""Direct installation and bounded JS/TS/JSX execution of Claude Mods packages.

Compatibility is explicit: unsupported events/APIs are reported. Shell hooks,
MCP processes and Node imports never execute as an accidental side effect.
"""

import asyncio
import json
import re
import shutil
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import quickjs
from langgraph.errors import GraphBubbleUp
from pydantic_core import to_jsonable_python

from app.plugins.manifest import Manifest, safe_path
from app.plugins.runtime import EVENTS, sdk_call

ROOT = Path(__file__).parent
MOD_ADAPTER_VERSION = 2


def convert_mod(target: Path):
    if not (target / ".claude-plugin/plugin.json").is_file():
        candidates = list(target.glob("*/.claude-plugin/plugin.json"))
        if len(candidates) != 1:
            raise ValueError(
                "ZIP must contain plugin.json or .claude-plugin/plugin.json"
            )
        source = candidates[0].parent.parent
        for path in source.iterdir():
            destination = target / path.name
            if destination.exists():
                raise ValueError("Ambiguous Claude plugin archive root")
            shutil.move(path, destination)
        source.rmdir()
    original = json.loads((target / ".claude-plugin/plugin.json").read_text())
    hooks_path = original.get("hooks", "hooks/hooks.json")
    if not isinstance(hooks_path, str):
        raise ValueError("Claude Mods hooks must reference a hooks.json file")
    hooks_file = target / safe_path(hooks_path)
    hooks = json.loads(hooks_file.read_text())
    modules = hooks.get("modules", [])
    if not modules:
        raise ValueError(
            "Claude plugin has no Mod modules; shell hooks alone are not supported"
        )
    resolved = []
    for module in modules:
        entry = (hooks_file.parent / module).resolve()
        if not entry.is_relative_to(target.resolve()) or not entry.is_file():
            raise ValueError("Claude Mod module is missing or outside the package")
        resolved.append(entry.relative_to(target).as_posix())
    name = original.get("name", "")
    identity = re.sub("[^a-z0-9-]", "-", name.lower()).strip("-")
    if not identity or not identity[0].isalpha():
        identity = "mod-" + identity
    identity = identity[:64]
    version = re.match(r"(\d+\.\d+\.\d+)", original.get("version", "1.0.0"))
    settings = []
    warnings = []
    for key, spec in original.get("userConfig", {}).items():
        kind = spec.get("type", "string")
        kind = {"number": "number", "boolean": "boolean", "string": "string"}.get(
            kind, "json"
        )
        default = spec.get(
            "default", {"number": 0, "boolean": False, "string": ""}.get(kind, None)
        )
        settings.append(
            {
                "key": key,
                "label": spec.get("title", key),
                "type": kind,
                "default": default,
                "secret": spec.get("sensitive", False),
                "description": spec.get("description", ""),
            }
        )
    if hooks.get("hooks"):
        warnings.append(
            "Classic shell/HTTP/prompt hooks are not executed; only modules are imported."
        )
    for key in ("mcpServers", "agents", "commands", "skills"):
        if original.get(key) or (target / key).exists():
            warnings.append(
                f"Claude component {key} is preserved in the package but not automatically activated."
            )
    sources = "\n".join(
        p.read_text()
        for p in target.rglob("*")
        if p.suffix in {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}
        and p.is_file()
        and "frontend" not in p.relative_to(target).parts
    )
    if re.search(r"\$\s*\.\s*process\s*\.", sources):
        warnings.append(
            "Unsupported API: $.process (no shell or subprocess execution host)."
        )
    if re.search(r"tool\s*:\s*['\"]Bash['\"]", sources):
        warnings.append(
            "Unavailable tool: Bash. OpenFic has no built-in Bash tool; shell interception is inactive."
        )
    hosts = sorted(
        {
            urlsplit(url).hostname
            for url in re.findall(r'https?://[^\s\'"`<>]+', sources)
            if urlsplit(url).hostname
        }
    )
    native = {
        "id": identity,
        "name": name,
        "version": version[1] if version else "1.0.0",
        "api_version": 1,
        "description": original.get("description", ""),
        "author": original.get("author", {}).get("name", "")
        if isinstance(original.get("author"), dict)
        else str(original.get("author", "")),
        "format": "claude-mod",
        "capabilities": [
            "agent.hooks",
            "agent.tools",
            "agent.models",
            "storage",
            "files",
            "events",
            "ui",
            "network",
            "projects.read",
            "chapters.read",
            "notes.read",
            "sessions.read",
        ],
        "network_hosts": hosts,
        "settings": settings,
        "views": [
            {
                "id": "mod",
                "title": name,
                "entry": "frontend/mod.html",
                "slot": "sidebar.extensions",
            }
        ],
        "compatibility": {
            "modules": resolved,
            "originalName": name,
            "originalVersion": original.get("version"),
            "warnings": warnings,
            "runtime": "QuickJS + Sucrase",
            "mode": "best-effort",
            "adapterVersion": MOD_ADAPTER_VERSION,
            "documentMapping": "Chapter/note creation and body edits use virtual Write/Edit events; no host filesystem access.",
        },
    }
    if "AbovePrompt" in sources and not any(
        "$.process" in warning for warning in warnings
    ):
        native["views"] = [
            {
                "id": "band",
                "title": name,
                "entry": "frontend/mod.html",
                "slot": "assistant.above-prompt",
                "height": 100,
            }
        ]
    manifest = Manifest.model_validate(native)
    (target / "plugin.json").write_text(manifest.model_dump_json(indent=2))
    frontend = target / "frontend"
    frontend.mkdir(exist_ok=True)
    (frontend / "mod.html").write_text(
        '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="mod.css"><script src="../../sdk.js" defer></script><script src="mod.js" defer></script></head><body><main><h1 id="title">Claude Mod</h1><p id="status" role="status"></p><div id="commands"></div><section id="render"></section></main></body></html>'
    )
    shutil.copyfile(ROOT / "mod-view.js", frontend / "mod.js")
    (frontend / "mod.css").write_text(
        "body{font:14px system-ui;margin:0;background:#fafafa;color:#242424}main{padding:20px;max-width:1000px;margin:auto}button,input,select{font:inherit;padding:7px;margin:4px;border:1px solid #bbb;border-radius:5px}pre{white-space:pre-wrap}#status{white-space:pre-wrap}#status:empty{display:none}a{color:#6650c8}html[data-theme=dark] body{background:#181818;color:#eee}html[data-embedded=true] body{background:transparent;font:12px/1.5 ui-monospace,monospace;overflow-x:hidden}html[data-embedded=true] main{padding:0}section[data-component=Pane]{border:1px solid #8885;border-radius:8px;padding:10px;margin:4px 0}section[data-component=Pane] button{padding:4px 8px}"
    )


class ModRuntime:
    def __init__(self, host, plugin, registration):
        self.host, self.plugin, self.registration = host, plugin, registration
        self.js = quickjs.Context()
        self.js.set_memory_limit(96 * 1024 * 1024)
        self.js.set_max_stack_size(1024 * 1024)
        self.js.set_time_limit(1)
        self.lock = asyncio.Lock()
        self.js.eval((ROOT / "vendor/transpiler.js").read_text())
        self.js.eval((ROOT / "mod-runtime.js").read_text())
        self.js.eval(
            f"__options={json.dumps(plugin.settings)}; __info={json.dumps({'name': plugin.manifest.compatibility['originalName']})}"
        )
        base = host.root / plugin.manifest.id
        for path in sorted(base.rglob("*")):
            if path.suffix == ".json" and path.is_file():
                value = json.loads(path.read_text())
                name = path.relative_to(base).as_posix()
                self.js.eval(
                    f"__modules[{json.dumps(name)}]=function(module){{module.exports={json.dumps(value)}}}"
                )
                continue
            if (
                path.suffix
                not in {".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts", ".cts", ".tsx"}
                or not path.is_file()
                or "frontend" in path.relative_to(base).parts
                or path.name.endswith(".d.ts")
            ):
                continue
            source = path.read_text()
            if len(source) > 1_000_000:
                raise ValueError("Mod source exceeds 1 MB")
            compiled = self.js.eval(f"__transpile({json.dumps(source)})")
            name = path.relative_to(base).as_posix()
            self.js.eval(
                f"__modules[{json.dumps(name)}]=function(module,exports,require){{\n{compiled}\n}}"
            )
        for entry in plugin.manifest.compatibility["modules"]:
            self.js.eval(
                f"__require({json.dumps('./' + entry)}).register(on,__options)"
            )

    async def invoke(self, name, payload, context, next_handler=None):
        async with self.lock:
            request_id = uuid.uuid4().hex
            self.js.eval(f"__hasContinuation={json.dumps(next_handler is not None)}")
            self.js.eval(
                f"__begin({json.dumps(request_id)},{json.dumps(name)},{json.dumps(to_jsonable_python(payload))})"
            )
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                for _ in range(100):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Claude Mod hook exceeded 25 seconds")
                    if not self.js.execute_pending_job():
                        break
                queue = json.loads(self.js.eval("__drain()"))
                for item in queue:
                    try:
                        if item["method"] == "compat.next":
                            assert next_handler is not None
                            value = await next_handler(item["args"])
                        else:
                            value = await self.bridge(
                                context, item["method"], item["args"]
                            )
                        error = None
                    except GraphBubbleUp:
                        # Approval/question interrupts belong to LangGraph. A
                        # JavaScript Error would turn a resumable pause into a
                        # failed tool result and lose the approval flow.
                        if item["id"]:
                            self.js.eval(f"delete __waiters[{json.dumps(item['id'])}]")
                        raise
                    except Exception as exc:
                        value, error = None, str(exc)
                    if item["id"]:
                        self.js.eval(
                            f"__settle({json.dumps(item['id'])},{json.dumps(to_jsonable_python(value))},{json.dumps(error)})"
                        )
                result = json.loads(self.js.eval(f"__take({json.dumps(request_id)})"))
                if result:
                    if result.get("error"):
                        raise ValueError(result["error"])
                    return result.get("value")
                await asyncio.sleep(0)
            raise TimeoutError("Claude Mod hook exceeded 25 seconds")

    async def bridge(self, context, method, args):
        if method == "compat.session.usage":
            from app.plugins.mod_events import session_usage

            return await session_usage(context)
        if method == "compat.ui":
            self.host.emit(args["event"], args.get("data", {}), self.plugin.manifest.id)
            return None
        if method == "compat.tools":
            from app.plugins.runtime import plugin_tools

            return [
                {"name": t.name, "description": t.description} for t in plugin_tools({})
            ]
        if method == "compat.sleep":
            await asyncio.sleep(min(max(args.get("ms", 0) / 1000, 0), 10))
            return None
        if method == "compat.tool.call":
            raise PermissionError(
                "Calling arbitrary host tools from Mods is unsupported; use registered plugin tools"
            )
        return await sdk_call(context, method, args)

    async def inspect(self, context, params):
        data = json.loads(
            self.js.eval(
                "JSON.stringify({commands:__commands,tools:__tools,panes:__panes})"
            )
        )
        trees = []
        components = (
            (["Pane"] if data["panes"] else []) + ["AbovePrompt"]
            if params.get("slot") == "assistant.above-prompt"
            else ["Pane", "AbovePrompt", "Spinner"]
        )
        requests = [
            (component, pane.get("id", "mod"))
            for component in components
            for pane in (
                (data["panes"] or [{"id": "mod"}])
                if component == "Pane"
                else [{"id": "mod"}]
            )
        ]

        async def fallback(event):
            return None

        for component, request_id in requests:
            rendered = await self.invoke(
                "ui.render",
                {
                    "component": component,
                    "surface": "desktop",
                    "requestId": request_id,
                    "bodyColumns": min(max(int(params.get("columns", 100)), 20), 240),
                    "maxRows": 24,
                    "hasSurvey": False,
                    "props": {
                        "title": self.plugin.manifest.name,
                        "word": "OpenFic",
                        "suffix": "",
                        "view": {},
                        "bodyColumns": 100,
                    },
                },
                context,
                fallback,
            )
            trees.append(
                {"component": component, "requestId": request_id, "tree": rendered}
            )
        return {
            **data,
            "trees": trees,
            "compatibility": self.plugin.manifest.compatibility,
        }


async def activate_mod(host, plugin, registration):
    runtime = ModRuntime(host, plugin, registration)
    context = host.context(plugin.manifest.id, None)
    await runtime.invoke(
        "session.start", {"sessionId": None, "projectId": None}, context
    )
    hooks = json.loads(runtime.js.eval("JSON.stringify(__hooks.map(h=>h.event))"))
    supported = sorted(EVENTS if "*" in hooks else set(hooks) & EVENTS)
    unsupported = sorted(
        set(hooks)
        - EVENTS
        - {"*", "command.run", "command.describe", "ui.resolve", "ui.close"}
    )
    plugin.manifest.compatibility["supported"] = supported
    plugin.manifest.compatibility["warnings"] = [
        *plugin.manifest.compatibility.get("warnings", []),
        *[f"Unsupported event: {event}" for event in unsupported],
    ]
    for event in supported:

        async def hook(context, data, next_handler, event=event):
            if event == "tool.call" and data.get("tool", "").startswith(
                f"plugin_{plugin.manifest.id.replace('-', '_')}_"
            ):
                return await next_handler(data)
            if event == "tool.call":
                from app.plugins.mod_events import tool_event

                translated, restore = tool_event(data, context.runtime)

                async def continuation(value):
                    return await next_handler(restore(value))

                return await runtime.invoke(event, translated, context, continuation)
            return await runtime.invoke(event, data, context, next_handler)

        registration.register_hook(event, hook)
    descriptors = json.loads(runtime.js.eval("JSON.stringify(__tools)"))
    for spec in descriptors:
        short = re.sub("[^a-z0-9_]", "_", spec["name"].lower())[:40]

        async def tool(context, params, name=spec["name"]):
            return await runtime.invoke(
                "tool.call",
                {
                    "tool": f"mcp__{plugin.manifest.compatibility['originalName']}__{name}",
                    "input": params,
                },
                context,
            )

        registration.register_tool(
            short,
            spec.get("description", "Claude Mod tool"),
            spec.get("inputSchema", {"type": "object"}),
            tool,
        )
    registration.register_command("mod.inspect", runtime.inspect)

    async def command(context, params):
        return await runtime.invoke("command.run", params, context)

    async def action(context, params):
        if not runtime.js.eval(f"Boolean(__actions[{json.dumps(params.get('id'))}])"):
            return await runtime.invoke(
                params.get("event", "ui.press"), params, context
            )
        return await runtime.invoke("action", params, context)

    async def close(context, params):
        pane_id = params["id"]
        runtime.js.eval(
            f"__panes=__panes.filter(pane=>pane.id!=={json.dumps(pane_id)})"
        )
        result = await runtime.invoke(
            "ui.close", {"id": pane_id, "requestId": pane_id}, context
        )
        host.emit("ui.invalidate", {}, plugin.manifest.id)
        return result

    registration.register_command("mod.command", command)
    registration.register_command("mod.action", action)
    registration.register_command("mod.close", close)
