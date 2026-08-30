from pathlib import Path


def test_docker_runtime_installs_openfic_project_metadata() -> None:
    dockerfile = (Path(__file__).resolve().parents[2] / "Dockerfile").read_text(encoding="utf-8")
    source_copy = dockerfile.index("COPY backend/ ./")

    assert "uv sync --frozen --no-dev\n" in dockerfile[source_copy:]
