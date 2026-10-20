"""Offline plugin diagnostics. Never import or execute plugin Python code."""

import ast
import json
from html.parser import HTMLParser
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urljoin, unquote

from app.plugins.declarative import (
    resolve_component,
    validate_document,
    validate_property,
)
from app.plugins.packages import build_package, source_files, extract_package


def check_plugin(source: Path, *, documents=(), run_checks=False) -> dict:
    source = source.expanduser().resolve()
    report = {
        "source": str(source),
        "pluginId": None,
        "diagnostics": [],
        "checks": [],
        "coverage": {"staticNodes": 0, "dynamicValues": 0, "documents": 0},
    }

    def issue(code, message, path="plugin.json", line=None, level="error"):
        report["diagnostics"].append(
            {
                "code": code,
                "severity": level,
                "file": str(path),
                "line": line,
                "message": str(message)[:2000],
            }
        )

    with tempfile.TemporaryDirectory(prefix="openfic-plugin-check-") as temporary:
        root = Path(temporary) / "package"
        root.mkdir()
        try:
            if source.is_file() and source.stat().st_size > 20 * 1024 * 1024:
                raise ValueError("Package exceeds 20 MiB")
            content = source.read_bytes() if source.is_file() else build_package(source)
            manifest = extract_package(content, root)
            report["pluginId"] = manifest.id
        except Exception as error:
            # Validation errors can embed input/default secrets. Never emit input values.
            message = (
                "; ".join(
                    ".".join(map(str, e["loc"])) + ": " + e["msg"]
                    for e in error.errors(include_input=False)
                )
                if hasattr(error, "errors")
                else str(error)
            )
            issue("package.invalid", message)
            report["ok"] = False
            return report
        files = list(source_files(root))

        class Resources(HTMLParser):
            def __init__(self):
                super().__init__()
                self.references = []

            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                field = (
                    "src"
                    if tag in {"script", "img", "source"}
                    else "href"
                    if tag == "link"
                    else None
                )
                if field and values.get(field):
                    self.references.append((values[field], self.getpos()[0]))

        for view in manifest.views:
            if view.renderer != "iframe":
                continue
            html = root / view.entry
            parser = Resources()
            parser.feed(html.read_text(encoding="utf-8", errors="replace"))
            prefix = "/plugin-assets/ticket/plugin/assets/"
            for reference, line in parser.references:
                if reference.startswith(("/", "#")) or urlsplit(reference).scheme:
                    continue
                url = urlsplit(
                    urljoin(
                        "https://plugin.invalid"
                        + prefix
                        + view.entry.removeprefix("frontend/"),
                        reference,
                    )
                )
                if url.path == "/plugin-assets/ticket/sdk.js":
                    continue
                relative = unquote(url.path.removeprefix(prefix))
                file = (root / "frontend" / relative).resolve()
                if (
                    not url.path.startswith(prefix)
                    or not file.is_relative_to(root / "frontend")
                    or not file.is_file()
                ):
                    issue(
                        "frontend.asset",
                        "Referenced HTML resource is missing or outside the plugin frontend: "
                        + reference,
                        view.entry,
                        line,
                    )
        trees = {}
        for path in files:
            if path.suffix == ".py":
                try:
                    trees[path.relative_to(root).as_posix()] = ast.parse(
                        path.read_text(encoding="utf-8"),
                        filename=str(path.relative_to(root)),
                    )
                except (SyntaxError, UnicodeError) as error:
                    issue(
                        "python.syntax",
                        getattr(error, "msg", "Invalid UTF-8 source"),
                        path.relative_to(root),
                        getattr(error, "lineno", None),
                    )
        functions = {
            node.name: node
            for tree in trees.values()
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        commands = {}
        dynamic_registration = False
        for tree in trees.values():
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "register_command"
                ):
                    if (
                        len(node.args) >= 2
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)
                        and isinstance(node.args[1], ast.Name)
                    ):
                        commands[node.args[0].value] = node.args[1].id
                    else:
                        dynamic_registration = True
        if manifest.backend:
            for view in manifest.views:
                if view.renderer == "declarative":
                    for command in [view.render, view.action]:
                        if command not in commands:
                            issue(
                                "ui.command",
                                "View "
                                + view.id
                                + " command not statically registered: "
                                + command,
                                level="warning"
                                if dynamic_registration or not commands
                                else "error",
                            )
        known_actions = set()
        for view in manifest.views:
            function = functions.get(commands.get(view.action))
            if function is None:
                continue
            aliases = set()

            def is_action_id(node):
                return (
                    isinstance(node, ast.Subscript)
                    and isinstance(node.slice, ast.Constant)
                    and node.slice.value == "id"
                ) or (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "id"
                )

            for node in ast.walk(function):
                if isinstance(node, ast.Assign) and is_action_id(node.value):
                    aliases.update(
                        target.id
                        for target in node.targets
                        if isinstance(target, ast.Name)
                    )
            for node in ast.walk(function):
                if isinstance(node, ast.Compare) and (
                    is_action_id(node.left)
                    or isinstance(node.left, ast.Name)
                    and node.left.id in aliases
                ):
                    for comparator in node.comparators:
                        try:
                            values = ast.literal_eval(comparator)
                            known_actions.update(
                                [values]
                                if isinstance(values, str)
                                else [v for v in values if isinstance(v, str)]
                            )
                        except (ValueError, TypeError):
                            pass
        action_ids = []
        for name, tree in trees.items():
            constants = {}
            for item in tree.body:
                if isinstance(item, (ast.Assign, ast.AnnAssign)):
                    try:
                        value = ast.literal_eval(item.value)
                        targets = (
                            item.targets
                            if isinstance(item, ast.Assign)
                            else [item.target]
                        )
                        for target in targets:
                            if isinstance(target, ast.Name):
                                constants[target.id] = value
                    except (ValueError, TypeError):
                        pass

            def literal(item):
                if isinstance(item, ast.Name) and item.id in constants:
                    return constants[item.id]
                return ast.literal_eval(item)

            builders = set()
            for function in ast.walk(tree):
                if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if function.args.args:
                    first = function.args.args[0].arg
                    for ret in ast.walk(function):
                        if isinstance(ret, ast.Return) and isinstance(
                            ret.value, ast.Dict
                        ):
                            for key, val in zip(ret.value.keys, ret.value.values):
                                if (
                                    isinstance(key, ast.Constant)
                                    and key.value == "type"
                                    and isinstance(val, ast.Name)
                                    and val.id == first
                                ):
                                    builders.add(function.name)
            for item in ast.walk(tree):
                component = None
                props = {}
                if (
                    isinstance(item, ast.Call)
                    and isinstance(item.func, ast.Name)
                    and item.func.id in builders
                    and item.args
                ):
                    try:
                        component = literal(item.args[0])
                    except (ValueError, TypeError):
                        continue
                    for keyword in item.keywords:
                        if keyword.arg:
                            props[keyword.arg] = keyword.value
                        else:
                            try:
                                props.update(
                                    {
                                        key: ast.Constant(value=value)
                                        for key, value in literal(keyword.value).items()
                                    }
                                )
                            except (ValueError, TypeError, AttributeError):
                                report["coverage"]["dynamicValues"] += 1
                elif isinstance(item, ast.Dict):
                    fields = {
                        key.value: val
                        for key, val in zip(item.keys, item.values)
                        if isinstance(key, ast.Constant) and isinstance(key.value, str)
                    }
                    try:
                        component = literal(fields["type"])
                    except (KeyError, ValueError, TypeError):
                        continue
                    # JSON Schema and business payloads also have a "type" field.
                    # Treat bare dictionaries as UI only for known component names.
                    if "props" not in fields and "children" not in fields:
                        try:
                            resolve_component(component)
                        except (ValueError, TypeError):
                            continue
                    raw = fields.get("props")
                    if isinstance(raw, ast.Dict):
                        props = {
                            key.value: value
                            for key, value in zip(raw.keys, raw.values)
                            if isinstance(key, ast.Constant)
                            and isinstance(key.value, str)
                        }
                if not isinstance(component, str):
                    continue
                report["coverage"]["staticNodes"] += 1
                try:
                    _, _, definition = resolve_component(component)
                    missing = set(definition.get("capabilities", [])) - set(
                        manifest.capabilities
                    )
                    if missing:
                        issue(
                            "ui.capability",
                            component + " requires " + ", ".join(sorted(missing)),
                            name,
                            item.lineno,
                        )
                    for prop, expression in props.items():
                        spec = definition["props"].get(prop)
                        if prop == "children":
                            continue
                        if spec is None and not prop.startswith(("aria-", "data-")):
                            issue(
                                "ui.prop",
                                f"{component}: unknown property {prop}",
                                name,
                                item.lineno,
                            )
                            continue
                        try:
                            value = literal(expression)
                        except (ValueError, TypeError):
                            report["coverage"]["dynamicValues"] += 1
                            continue
                        try:
                            if spec:
                                validate_property(prop, value, spec)
                                if spec["type"] == "event" and isinstance(value, str):
                                    action_ids.append((value, name, item.lineno))
                            if (
                                component in {"Image", "Project.Image"}
                                and prop == "asset"
                            ):
                                asset = (root / "frontend" / value).resolve()
                                if (
                                    not asset.is_relative_to(root / "frontend")
                                    or not asset.is_file()
                                ):
                                    issue(
                                        "ui.asset",
                                        "Image asset is missing or outside frontend/",
                                        name,
                                        item.lineno,
                                    )
                        except (ValueError, TypeError, KeyError):
                            issue(
                                "ui.value",
                                f"{component}: invalid value for {prop}",
                                name,
                                item.lineno,
                            )
                except ValueError:
                    issue(
                        "ui.component",
                        "Unknown component: " + component,
                        name,
                        item.lineno,
                    )
            # Literal HTTP URLs can be checked without evaluating plugin code.
            for item in ast.walk(tree):
                if (
                    isinstance(item, ast.Call)
                    and isinstance(item.func, ast.Attribute)
                    and item.func.attr == "request"
                    and isinstance(item.func.value, ast.Attribute)
                    and item.func.value.attr == "http"
                ):
                    if "network" not in manifest.capabilities:
                        issue(
                            "network.capability",
                            "HTTP requires network capability",
                            name,
                            item.lineno,
                        )
                    if len(item.args) > 1:
                        try:
                            host = urlsplit(literal(item.args[1])).hostname
                            if host and host not in manifest.network_hosts:
                                issue(
                                    "network.host",
                                    "Literal HTTP hostname is not declared in network_hosts",
                                    name,
                                    item.lineno,
                                )
                        except (ValueError, TypeError):
                            pass
        fixtures = []
        config = root / "plugin.dev.json"
        if config.exists():
            try:
                dev = json.loads(config.read_text())
                if not isinstance(dev, dict) or not isinstance(
                    dev.get("fixtures", []), list
                ):
                    raise ValueError("fixtures must be a list")
                for fixture in dev.get("fixtures", []):
                    file = (root / fixture["file"]).resolve()
                    if not file.is_relative_to(root) or not file.is_file():
                        raise ValueError("Fixture must exist inside the plugin")
                    if fixture.get("view") not in {
                        v.id for v in manifest.views if v.renderer == "declarative"
                    }:
                        raise ValueError(
                            "Fixture references an unknown declarative view"
                        )
                    fixtures.append(file)
            except (ValueError, TypeError, KeyError) as error:
                issue("dev.config", error, "plugin.dev.json")
        fixtures.extend(Path(file).resolve() for file in documents)
        report["coverage"]["actionIdsChecked"] = sum(
            1 for value, _, _ in action_ids if value in known_actions
        )
        report["coverage"]["actionIdsUnverified"] = sum(
            1 for value, _, _ in action_ids if value not in known_actions
        )
        for action_id, file, line in sorted(set(action_ids)):
            if known_actions and action_id not in known_actions:
                issue(
                    "ui.action.unverified",
                    "Action ID not found in statically recognized handler branches: "
                    + action_id,
                    file,
                    line,
                    level="warning",
                )
        css_documents = []
        for file in fixtures:
            try:
                document = json.loads(file.read_text())
                validate_document(document, capabilities=manifest.capabilities)
                report["coverage"]["documents"] += 1
                css_documents.append((str(file), document.get("css", "")))
            except (OSError, ValueError, TypeError, KeyError) as error:
                issue("ui.document", error, file.name)
        for name, tree in trees.items():
            for item in tree.body:
                if isinstance(item, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id in {"CSS", "STYLES"}
                    for t in item.targets
                ):
                    try:
                        css = ast.literal_eval(item.value)
                        if isinstance(css, str):
                            css_documents.append((name, css))
                    except (ValueError, TypeError):
                        pass
        css_tool = shutil.which("openfic-plugin-ui")
        repository_tool = (
            Path(__file__).resolve().parents[3]
            / "frontend/node_modules/@openfic/plugin-devtools/cli.mjs"
        )
        command = (
            [css_tool]
            if css_tool
            else (
                [shutil.which("node"), str(repository_tool)]
                if shutil.which("node") and repository_tool.exists()
                else None
            )
        )
        if css_documents and command:
            try:
                result = subprocess.run(
                    [*command, "css", "--json"],
                    input=json.dumps(css_documents),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                for finding in json.loads(result.stdout)["diagnostics"]:
                    issue(**finding)
                report["checks"].append(
                    {
                        "name": "css",
                        "status": "passed" if result.returncode == 0 else "failed",
                    }
                )
            except (OSError, ValueError, subprocess.TimeoutExpired):
                issue(
                    "css.unavailable",
                    "CSS compiler could not run; install @openfic/plugin-devtools",
                    level="warning",
                )
        elif css_documents:
            issue(
                "css.not-run",
                "CSS was not checked; install @openfic/plugin-devtools and Node.js",
                level="warning",
            )
        if any(v.renderer == "declarative" for v in manifest.views) and not fixtures:
            issue(
                "ui.dynamic",
                "No UI fixtures supplied. Dynamic render output and action behavior require runtime validation.",
                level="warning",
            )
        # ZIPs contain artifacts, not necessarily the original lint projects.
        live_root = source if source.is_dir() else None
        if live_root and run_checks:
            python_files = [str(live_root / name) for name in trees]
            ruff = shutil.which("ruff") or str(Path(sys.executable).parent / "ruff")
            if python_files and Path(ruff).is_file():
                entry = {"name": "ruff", "status": "failed"}
                try:
                    result = subprocess.run(
                        [ruff, "check", "--output-format=json", *python_files],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    for finding in json.loads(result.stdout or "[]"):
                        issue(
                            "ruff." + str(finding["code"]),
                            finding["message"],
                            str(Path(finding["filename"]).relative_to(live_root)),
                            finding["location"]["row"],
                        )
                    entry["status"] = "passed" if result.returncode == 0 else "failed"
                    if result.returncode:
                        entry["output"] = (result.stdout + result.stderr)[-12000:]
                        issue(
                            "python.lint",
                            "Ruff reported errors or could not load its configuration",
                        )
                except (
                    OSError,
                    ValueError,
                    KeyError,
                    TypeError,
                    subprocess.TimeoutExpired,
                ):
                    issue(
                        "python.lint",
                        "Ruff unavailable, timed out or returned invalid diagnostics",
                    )
                report["checks"].append(entry)
            elif python_files:
                issue("python.lint.not-run", "Ruff is not installed", level="warning")
        projects = [file for file in files if file.name == "package.json"]
        js_files = any(
            file.suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs"} for file in files
        )
        if js_files and not projects:
            issue(
                "frontend.unconfigured",
                "No package.json lint/type-check scripts found; frontend source has not been linted or type-checked",
                level="warning",
            )
        for project in projects:
            try:
                scripts = json.loads(project.read_text()).get("scripts", {})
                if not isinstance(scripts, dict) or any(
                    not isinstance(value, str) for value in scripts.values()
                ):
                    raise ValueError("scripts must map names to command strings")
            except (ValueError, AttributeError):
                issue(
                    "frontend.config", "Invalid package.json", project.relative_to(root)
                )
                continue
            for label, candidates in [
                ("lint", ["lint"]),
                ("types", ["type-check", "typecheck"]),
            ]:
                script = next((name for name in candidates if name in scripts), None)
                if not script:
                    issue(
                        "frontend." + label + ".unconfigured",
                        "No " + label + " script configured",
                        project.relative_to(root),
                        level="warning",
                    )
                    continue
                entry = {
                    "name": str(project.relative_to(root).parent) + ":" + script,
                    "status": "not-run",
                }
                if live_root and run_checks:
                    try:
                        result = subprocess.run(
                            [
                                shutil.which("npm") or "npm",
                                "run",
                                script,
                                "--if-present",
                            ],
                            cwd=live_root / project.parent.relative_to(root),
                            capture_output=True,
                            text=True,
                            timeout=120,
                        )
                        entry["status"] = (
                            "passed" if result.returncode == 0 else "failed"
                        )
                        if result.returncode:
                            issue(
                                "frontend." + label,
                                "Project script failed: " + script,
                                project.relative_to(root),
                            )
                            entry["output"] = (result.stdout + result.stderr)[-12000:]
                    except (OSError, subprocess.TimeoutExpired):
                        entry["status"] = "failed"
                        issue(
                            "frontend." + label,
                            "Project script unavailable or timed out",
                            project.relative_to(root),
                        )
                report["checks"].append(entry)
        if not run_checks:
            report["checks"].append(
                {
                    "name": "external lint/type-check",
                    "status": "not-run",
                    "reason": "Use --run-checks to execute project scripts and Ruff",
                }
            )
    report["ok"] = not any(
        item["severity"] == "error" for item in report["diagnostics"]
    )
    return report
