from unittest.mock import AsyncMock

import asyncpg
import pytest
from fastapi import FastAPI
from starlette.requests import Request

from app.db.pool import connection, lifespan


@pytest.fixture
def application(settings):
    app = FastAPI(lifespan=lifespan)
    app.state.settings = settings
    return app


async def test_startup_failure_prevents_serving(application, monkeypatch):
    factory = AsyncMock(side_effect=OSError("Database unavailable"))
    monkeypatch.setattr("app.db.pool.asyncpg.create_pool", factory)
    with pytest.raises(OSError):
        async with lifespan(application):
            pytest.fail("Startup must fail without a database")
    factory.assert_awaited_once()


@pytest.mark.parametrize("close_timeout", [False, True])
async def test_shutdown_closes_or_terminates_pool(application, pool, monkeypatch, close_timeout):
    pool.close.side_effect = TimeoutError if close_timeout else None
    factory = AsyncMock(return_value=pool)
    monkeypatch.setattr("app.db.pool.asyncpg.create_pool", factory)
    with pytest.raises(RuntimeError, match="body failed"):
        async with lifespan(application):
            assert application.state.pool is pool
            raise RuntimeError("body failed")
    pool.close.assert_awaited_once()
    assert pool.terminate.called == close_timeout
    assert factory.await_args.kwargs["max_size"] == application.state.settings.pool_size


async def test_connection_dependency_reuses_pool(application, pool):
    application.state.pool = pool
    generator = connection(Request({"type": "http", "app": application}))
    try:
        assert await anext(generator) is pool.acquire.return_value.__aenter__.return_value
    finally:
        await generator.aclose()
    pool.acquire.assert_called_once_with(timeout=2)
    pool.acquire.return_value.__aexit__.assert_awaited_once()


async def test_real_postgres_lifespan(application):
    from app.db.generated.health import health_probe

    async with lifespan(application):
        pool = application.state.pool
        async with pool.acquire() as conn:
            assert await health_probe(conn) == 1
        assert application.state.pool is pool
    with pytest.raises(asyncpg.InterfaceError):
        async with pool.acquire():
            pass
