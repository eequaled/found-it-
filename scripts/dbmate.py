"""Invoke the pinned dbmate binary without putting database secrets in argv."""
import asyncio
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


async def dbmate(url: str, command: str):
    process = await asyncio.create_subprocess_exec(
        str(ROOT / "node_modules/.bin/dbmate"), "--no-dump-schema",
        "--migrations-dir", str(ROOT / "migrations"), command,
        cwd=ROOT, env={**os.environ, "DATABASE_URL": url},
    )
    try:
        async with asyncio.timeout(60):
            result = await process.wait()
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if result:
        raise RuntimeError(f"dbmate {command} failed (exit {result})")
