"""Unified plugin packages and public resource boundaries."""

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.plugins.checker import check_plugin
from app.plugins.html import inject_sdk
from app.plugins.manifest import Manifest
from app.plugins.packages import build_package
from tests.plugins import test_host as host_tests

plugin_api = host_tests.plugin_api
pytestmark = pytest.mark.asyncio(loop_scope="module")


def archive(manifest, files):
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as z:
        z.writestr("plugin.json", json.dumps(manifest))
        for name, value in files.items():
            z.writestr(name, value)
    return content.getvalue()


def contract(**values):
    return {
        "id": "layout-test",
        "name": "Layout test",
        "version": "1.0.0",
        "api_version": 1,
        **values,
    }


@pytest.mark.parametrize(
    "values",
    [
        {"entry": "../main.py"},
        {"entry": "src/main.py", "resources": ["SRC"]},
        {"entry": "src/main.py", "resources": ["src"]},
        {"resources": ["plugin.json"]},
        {"resources": ["../private"]},
        {"resources": ["assets", "assets"]},
        {"views": [{"id": "panel", "title": "Panel", "entry": "web/view.html"}]},
        {"entry": "main.py", "backend": "another.py"},
    ],
)
async def test_manifest_rejects_ambiguous_or_private_public_paths(values):
    with pytest.raises(ValidationError):
        Manifest.model_validate(contract(**values))


@pytest.mark.parametrize(
    "entry,view",
    [
        ("main.py", "panel/index.html"),
        ("src/plugin.py", "build/custom/deep/view.html"),
    ],
)
async def test_arbitrary_layout_initializes_sdk_and_keeps_sources_private(
    plugin_api, session, entry, view
):
    host, api, _ = plugin_api
    public = str(Path(view).parent)
    manifest = contract(
        entry=entry,
        resources=[public, "images"],
        capabilities=["ui"],
        views=[{"id": "panel", "title": "Panel", "entry": view}],
    )
    parent = Path(entry).parent
    files = {
        entry: 'from .helpers import answer\ndef register(host):\n host.register_command("answer", answer)\n',
        str(
            parent / "helpers.py"
        ): 'async def answer(ctx, params):\n return "isolated helper"\n',
        view: '<!doctype html><!-- <head> is documentation, not markup --><html><head><meta charset="utf-8"></head><body><script src="./app.js"></script></body></html>',
        f"{public}/app.js": "OpenFic.ready.then(() => {});",
        "images/pixel.png": b"\x89PNG\r\n\x1a\n",
        "private.json": '{"private":true}',
    }
    await host.install(archive(manifest, files))
    await host.set_enabled("layout-test", True)
    assert await host.call("layout-test", "answer", {}, session) == "isolated helper"
    context = host.context("layout-test", session)
    assert (await context.assets.read("images/pixel.png"))["mime"] == "image/png"
    for name in [
        entry,
        str(parent / "helpers.py"),
        "private.json",
        "plugin.json",
        "images/../private.json",
    ]:
        assert (
            await api.get(f"/api/v1/plugins/layout-test/assets/{name}")
        ).status_code == 404
        with pytest.raises(ValueError):
            await context.assets.read(name)
    url = host.open_view("layout-test", "panel")
    assert url.endswith("/assets/" + view)
    response = await api.get(url)
    assert response.status_code == 200
    token = url.split("/")[2]
    assert response.text.index(f"/plugin-assets/{token}/sdk.js") < response.text.index(
        '<script src="./app.js"'
    )
    assert 'crossorigin="anonymous"' in response.text
    assert "connect-src 'none'" in response.headers["content-security-policy"]
    assert (await api.get(f"/plugin-assets/{token}/sdk.js")).status_code == 200
    assert (
        await api.get(f"/plugin-assets/{token}/other/assets/{view}")
    ).status_code == 404
    assert (host.root / "layout-test" / view).read_text() == files[view]
    await host.close()
    await host.start()
    assert await host.call("layout-test", "answer", {}, session) == "isolated helper"


async def test_package_modules_are_isolated_cleaned_and_reload_from_new_helpers(
    plugin_api, session
):
    host, _, _ = plugin_api
    entry = 'from .helper import label\nasync def value(ctx, params): return label\ndef register(host): host.register_command("value", value)\n'
    for identity in ["module-one", "module-two"]:
        await host.install(
            archive(
                contract(id=identity, entry="src/main.py"),
                {"src/main.py": entry, "src/helper.py": f'label = "{identity}"\n'},
            )
        )
        await host.set_enabled(identity, True)
    previous = host.get("module-one").module_name
    assert previous + ".helper" in sys.modules
    await host.install(
        archive(
            contract(id="module-one", version="1.1.0", entry="src/main.py"),
            {"src/main.py": entry, "src/helper.py": 'label = "new-helper"\n'},
        ),
        update_id="module-one",
    )
    assert not any(
        name == previous or name.startswith(previous + ".") for name in sys.modules
    )
    assert await host.call("module-one", "value", {}, session) == "new-helper"
    assert await host.call("module-two", "value", {}, session) == "module-two"
    namespace = host.get("module-one").module_name
    await host.set_enabled("module-one", False)
    assert not any(
        name == namespace or name.startswith(namespace + ".") for name in sys.modules
    )


async def test_source_checks_keep_dev_files_but_runtime_package_does_not(tmp_path):
    manifest = contract(
        entry="main.py",
        resources=["panel"],
        views=[{"id": "panel", "title": "Panel", "entry": "panel/#custom/view.html"}],
    )
    files = {
        "plugin.json": json.dumps(manifest),
        "main.py": "def register(host): pass\n",
        "panel/#custom/view.html": '<script src="./app.js"></script>',
        "panel/#custom/app.js": "OpenFic.ready.then(() => {});",
        "tests/test_example.py": "# developer test\n",
        "notes.txt": "development only",
        "plugin.dev.json": json.dumps(
            {"package": {"include": ["main.py", "panel"], "exclude": []}}
        ),
    }
    for name, value in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    with zipfile.ZipFile(io.BytesIO(build_package(tmp_path))) as z:
        assert set(z.namelist()) == {
            "plugin.json",
            "main.py",
            "panel/#custom/view.html",
            "panel/#custom/app.js",
        }
    # Excluded developer files do not consume the runtime archive's file budget.
    for index in range(520):
        (tmp_path / "tests" / f"fixture-{index}.txt").write_text("source only")
    assert check_plugin(tmp_path)["ok"]
    developer_test = tmp_path / "tests/test_example.py"
    developer_test.write_text("invalid Python syntax ?")
    assert any(
        d["code"] == "python.syntax" for d in check_plugin(tmp_path)["diagnostics"]
    )
    developer_test.write_text("# developer test")
    assert check_plugin(tmp_path)["ok"]
    (tmp_path / "plugin.dev.json").write_text(
        json.dumps({"package": {"include": ["main.py", "panel/#custom/view.html"]}})
    )
    report = check_plugin(tmp_path)
    assert not report["ok"] and any(
        d["code"] == "frontend.asset" for d in report["diagnostics"]
    )


@pytest.mark.parametrize(
    "document",
    [
        '<!doctype html><!-- <head> --><html><head><script src="app.js"></script></head></html>',
        '<script>const example="<head>";</script>',
        '<!DOCTYPE html>\n<html>\n<HEAD data-x="ok"><meta charset="utf-8"></HEAD></html>',
    ],
)
async def test_sdk_injection_parses_real_markup_and_precedes_application(document):
    result = inject_sdk(document, "/plugin-assets/token/sdk.js")
    injected = (
        '<script src="/plugin-assets/token/sdk.js" crossorigin="anonymous"></script>'
    )
    assert result.count(injected) == 1
    assert result.replace(injected, "") == document
    if "<script" in document:
        assert result.index(injected) <= document.index("<script")


async def test_watch_scripts_use_root_or_explicit_project_directories(tmp_path):
    from app.plugin_cli import resolve_script_directory
    from app.cli import build_parser

    for relative in ("tools", "another"):
        directory = tmp_path / relative
        directory.mkdir()
        (directory / "package.json").write_text(
            json.dumps({"scripts": {"watch": "a-build-tool"}})
        )
    with pytest.raises(ValueError, match="--script-dir"):
        resolve_script_directory(tmp_path, "watch")
    assert resolve_script_directory(tmp_path, "watch", "tools") == tmp_path / "tools"
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"watch": "root-build"}})
    )
    assert resolve_script_directory(tmp_path, "watch") == tmp_path
    with pytest.raises(ValueError, match="inside"):
        resolve_script_directory(tmp_path, "watch", "..")
    args = build_parser().parse_args(
        ["plugin", "dev", str(tmp_path), "--frontend-script", "watch"]
    )
    assert args.watch_script == "watch"

