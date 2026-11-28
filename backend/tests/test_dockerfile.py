from pathlib import Path


def test_frontend_installs_local_plugin_devtools() -> None:
    dockerfile = (Path(__file__).resolve().parents[2] / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.index("COPY packages/plugin-devtools/ /packages/plugin-devtools/") < dockerfile.index(
        "pnpm install --frozen-lockfile"
    )
    assert dockerfile.index(
        "COPY backend/app/plugins/ui-catalog.json /backend/app/plugins/ui-catalog.json"
    ) < dockerfile.index("RUN pnpm build")


def test_docker_runtime_installs_openfic_project_metadata() -> None:
    dockerfile = (Path(__file__).resolve().parents[2] / "Dockerfile").read_text(encoding="utf-8")
    source_copy = dockerfile.index("COPY backend/ ./")
    runtime_install_start = dockerfile.index(
        "# 安装当前项目以写入发行版元数据，供运行时读取版本号",
        source_copy,
    )
    runtime_install = dockerfile[runtime_install_start:]

    assert "uv sync --frozen --no-dev" in runtime_install
    assert "--no-install-project" not in runtime_install
