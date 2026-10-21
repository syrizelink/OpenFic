"""Repository wrapper around the same packager used by plugin check/dev/pack."""

import argparse
from runpy import run_path
from pathlib import Path


def build(source: Path, output: Path):
    module = (
        Path(__file__).resolve().parents[2] / "backend/app/plugins/package_builder.py"
    )
    build_package = run_path(str(module))["build_package"]

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(build_package(source))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.source, args.output)
