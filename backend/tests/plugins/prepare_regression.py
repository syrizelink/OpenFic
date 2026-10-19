"""Seed only the disposable regression_app server, never a production instance."""

import argparse
import io
import json
import zipfile
from pathlib import Path

import httpx


def prepare(backend: str, *, observer: bool = False):
    with httpx.Client(base_url=backend, timeout=60) as client:
        probe = client.get("/_e2e/drive")
        probe.raise_for_status()
        assert "files" in probe.json(), "Only tests.plugins.regression_app is supported"

        def request(method, path, **kwargs):
            response = client.request(method, "/api/v1" + path, **kwargs)
            response.raise_for_status()
            return response.json()

        ids = {}
        for kind in ["empty", "large"]:
            project = request(
                "POST", "/projects", data={"title": "原有功能回归-" + kind}
            )
            ids[kind] = project["id"]
            volume = request("GET", f"/projects/{project['id']}/volumes")[0]
            if kind == "large":
                for index in range(1, 16):
                    request(
                        "POST",
                        f"/projects/{project['id']}/chapters",
                        json={
                            "volume_id": volume["id"],
                            "title": f"回归章节{index}",
                            "content": "旅人穿过山谷，遇见了旧日的朋友。\n" * 70,
                            "word_count": 1120,
                        },
                    )
        provider = request(
            "POST",
            "/model-providers",
            data={
                "name": "Regression fixture",
                "provider_type": "openai_compatible",
                "url": backend + "/_e2e/regression/v1",
                "api_key": "test-only",
            },
        )
        ids["provider"] = provider["id"]
        model = request(
            "POST",
            "/models",
            json={
                "name": "Regression " + ids["empty"],
                "model_id": "sdk-test-model",
                "provider_id": provider["id"],
                "context_length": 64000,
            },
        )
        ids["model"] = model["id"]
        request(
            "PATCH",
            "/settings",
            json={
                "default_model": model["id"],
                "light_model": model["id"],
                "agent_bypass_tool_approval": False,
                "telemetry_enabled": False,
            },
        )
        if observer:
            fixture = (
                Path(__file__).resolve().parents[3]
                / "frontend/e2e/fixtures/plugin-regression"
            )
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                for path in fixture.rglob("*"):
                    if path.is_file() and "__pycache__" not in path.parts:
                        archive.writestr(
                            path.relative_to(fixture).as_posix(), path.read_bytes()
                        )
            response = client.post(
                "/api/v1/plugins",
                files={"file": ("probe.zip", buffer.getvalue(), "application/zip")},
                data={"trusted": "true"},
            )
            response.raise_for_status()
            request(
                "PATCH", "/plugins/regression-probe/enabled", json={"enabled": True}
            )
        return ids


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="http://127.0.0.1:8021")
    parser.add_argument("--output", required=True)
    parser.add_argument("--observer", action="store_true")
    options = parser.parse_args()
    Path(options.output).write_text(
        json.dumps(prepare(options.backend, observer=options.observer))
    )
