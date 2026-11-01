"""sqlc commands. Validation does not execute or download a codegen plugin."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "migrations"
QUERIES = ROOT / "app/db/queries"
GENERATED = ROOT / "app/db/generated"


def sqlc_binary():
    return (
        os.getenv("SQLC_BIN")
        or shutil.which("sqlc")
        or str(Path.home() / ".local/bin/sqlc")
    )


def validate():
    with tempfile.TemporaryDirectory() as directory:
        config = Path(directory) / "sqlc.json"
        config.write_text(
            json.dumps(
                {
                    "version": "2",
                    "sql": [
                        {
                            "engine": "postgresql",
                            "schema": str(SCHEMA),
                            "queries": str(QUERIES),
                        }
                    ],
                }
            )
        )
        subprocess.run([sqlc_binary(), "compile", "-f", str(config)], check=True)


def same_tree(left: Path, right: Path):
    if not left.is_dir() or not right.is_dir():
        return False

    # Exclude Python runtime caches, never source files (including untracked output).
    def files(root):
        return {
            p.relative_to(root)
            for p in root.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        }

    paths = files(left)
    return (
        bool(paths)
        and paths == files(right)
        and all((left / p).read_bytes() == (right / p).read_bytes() for p in paths)
    )


def check_generated():
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        for folder in [SCHEMA, QUERIES]:
            relative = folder.relative_to(ROOT)
            shutil.copytree(folder, work / relative)
        shutil.copy(ROOT / "sqlc.yaml", work / "sqlc.yaml")
        (work / ".tools").mkdir()
        shutil.copy(ROOT / ".tools/sqlc-gen-better-python.wasm", work / ".tools")
        subprocess.run([sqlc_binary(), "generate"], cwd=work, check=True)
        if not same_tree(GENERATED, work / GENERATED.relative_to(ROOT)):
            raise SystemExit(
                "Generated output missing or stale; run make generate and review the diff"
            )


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["validate"]:
        validate()
    elif sys.argv[1:] == ["check"]:
        check_generated()
    else:
        raise SystemExit("usage: python -m scripts.codegen validate|check")
