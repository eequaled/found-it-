"""Fetch the checksum-pinned upstream fixture artifact without vendoring it.

The v0.9.0 source tree includes a WASM fixture. It is a different build from the
release asset, so pin its own checksum rather than pretending they are identical.
"""

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = "1921a0dc8f5e518a90ecaf5d246f3c856aad9ad6"
SHA256 = "ea40a229077a701acb2d5282e95d8dd7cf9759ca8fe2558fe7b2fe0062f63627"


def prepare():
    reference = ROOT / "references/sqlc-gen-better-python"
    if not reference.exists():
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                "v0.9.0",
                "https://github.com/rayakame/sqlc-gen-better-python",
                str(reference),
            ],
            check=True,
        )
    revision = subprocess.check_output(
        ["git", "-C", str(reference), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != REVISION:
        raise SystemExit(
            "Reference revision differs from pinned generator; do not silently replace it"
        )
    data = (reference / "test/driver_asyncpg/sqlc-gen-better-python.wasm").read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit("Generator checksum mismatch")
    target = ROOT / ".tools/sqlc-gen-better-python.wasm"
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(data)


if __name__ == "__main__":
    prepare()
