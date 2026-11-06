import asyncio
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = app.state.settings
    # Fail startup rather than accept requests without a working database.
    pool = await asyncpg.create_pool(
        dsn=str(settings.database_url), min_size=1, max_size=settings.pool_size,
        timeout=5, command_timeout=10,
    )
    app.state.pool = pool
    try:
        yield
    finally:
        try:
            async with asyncio.timeout(10):
                await pool.close()
        except TimeoutError:
            pool.terminate()


async def connection(request: Request):
    async with request.app.state.pool.acquire(timeout=2) as conn:
        yield conn
