"""sqlc commands. Validation does not execute or download a codegen plugin."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "generation/schema"
QUERIES = ROOT / "generation/queries"
GENERATED = ROOT / "generation/generated"


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


def generate():
    subprocess.run([sqlc_binary(), "generate"], cwd=ROOT, check=True)


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["validate"]:
        validate()
    elif sys.argv[1:] == ["generate"]:
        generate()
    else:
        raise SystemExit("usage: python -m scripts.codegen validate|generate")
