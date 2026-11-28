"""Plugin check and package CLI handlers."""

import json
from pathlib import Path


def handle_plugin(args):
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
