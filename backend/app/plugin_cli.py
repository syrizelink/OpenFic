"""Plugin CLI handlers, kept lazy so development environment precedes app imports."""

from contextlib import suppress
import json
import os
from pathlib import Path
import subprocess
import sys


def handle_plugin(args):
    if args.plugin_command == "dev":
        return serve_development(args)
    from app.plugins.checker import check_plugin

    if args.plugin_command == "pack" and not Path(args.source).is_dir():
        raise SystemExit("Packing requires a source directory")
    report = check_plugin(
        Path(args.source), documents=args.ui, run_checks=args.run_checks
    )
    if args.strict and any(check["status"] == "not-run" for check in report["checks"]):
        report["diagnostics"].append(
            {
                "code": "checks.not-run",
                "severity": "error",
                "file": "plugin.json",
                "line": None,
                "message": "Strict checks require configured lint/type-check commands to run; use --run-checks",
            }
        )
        report["ok"] = False
    if args.strict and any(
        item["severity"] == "warning" for item in report["diagnostics"]
    ):
        report["ok"] = False
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Plugin: {report['pluginId'] or '(invalid)'}")
        for item in report["diagnostics"]:
            print(
                f"{item['severity'].upper()} {item['file']}:{item.get('line') or '-'} [{item['code']}] {item['message']}"
            )
        for check in report["checks"]:
            print(f"{check['name']}: {check['status']}")
        print("Static checks passed" if report["ok"] else "Checks failed")
    failed = (
        not report["ok"]
        or args.strict
        and any(item["severity"] == "warning" for item in report["diagnostics"])
    )
    if failed:
        raise SystemExit(1)
    if args.plugin_command == "pack":
        from app.plugins.packages import build_package

        output = Path(args.output).resolve()
        content = build_package(Path(args.source))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
        if not args.json:
            print(f"Package: {output}")


def serve_development(args):
    source = Path(args.source).expanduser().resolve()
    if not source.is_dir() or not (source / "plugin.json").is_file():
        raise SystemExit(
            "Development source must be a directory containing plugin.json"
        )
    data = (
        Path(args.data_dir).expanduser().resolve()
        if args.data_dir
        else source / ".openfic-dev"
    )
    if (
        data.is_relative_to(source)
        and ".openfic-dev" not in data.relative_to(source).parts
    ):
        raise SystemExit(
            "Development data inside the source must be under .openfic-dev/ so it is excluded from packages and watching"
        )
    marker = data / ".openfic-plugin-development"
    if data.exists() and any(data.iterdir()) and not marker.is_file():
        raise SystemExit(
            "Use an empty development data directory; existing application data is not accepted"
        )
    if marker.exists() and marker.read_text() != str(source):
        raise SystemExit(
            "This development data directory belongs to another plugin source"
        )
    data.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(source))
    os.environ["OPENFIC_DATA_DIR"] = str(data)
    os.environ["OPENFIC_PLUGIN_DEV_SOURCE"] = str(source)
    os.environ["OPENFIC_PLUGIN_DEVTOOLS"] = "1"
    # Preserve explicit auth preferences; bind development servers to loopback.
    os.environ["OPENFIC_SERVER_HOST"] = "127.0.0.1"
    os.environ["OPENFIC_SERVER_PORT"] = str(args.port)
    frontend = (args.frontend_url or f"http://127.0.0.1:{args.port}").rstrip("/")
    print(
        f"Plugin development: {frontend}/extensions/devtools\nData: {data}\nWatching: {source}",
        flush=True,
    )
    process = None
    if args.frontend_script:
        import shutil

        process = subprocess.Popen(
            [shutil.which("npm") or "npm", "run", args.frontend_script],
            cwd=source / "frontend",
            start_new_session=True,
        )
    try:
        from app.logging import configure_standard_logging

        configure_standard_logging()
        import uvicorn
        from app.main import app
        from app.cli import _get_uvicorn_loop_factory

        uvicorn.run(
            app,
            host="127.0.0.1",
            port=args.port,
            loop=_get_uvicorn_loop_factory(),
            log_config=None,
            access_log=False,
        )
    finally:
        if process:
            # npm often spawns a build watcher; terminate the whole process group.
            if sys.platform != "win32":
                import signal

                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
