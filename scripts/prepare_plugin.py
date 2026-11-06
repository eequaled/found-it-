"""Fetch the checksum-pinned upstream fixture artifact without vendoring it.

The v0.9.0 source tree includes a WASM fixture. It is a different build from the
release asset, so pin its own checksum rather than pretending they are identical.
Only the single WASM file is downloaded; the upstream repository is not cloned.
"""

import hashlib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = "1921a0dc8f5e518a90ecaf5d246f3c856aad9ad6"
SHA256 = "ea40a229077a701acb2d5282e95d8dd7cf9759ca8fe2558fe7b2fe0062f63627"
URL = (
    "https://raw.githubusercontent.com/rayakame/sqlc-gen-better-python/"
    f"{REVISION}/test/driver_asyncpg/sqlc-gen-better-python.wasm"
)


def prepare():
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit("Generator checksum mismatch")
    target = ROOT / ".tools/sqlc-gen-better-python.wasm"
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(data)


if __name__ == "__main__":
    prepare()
