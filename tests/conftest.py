import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings


@pytest.fixture
def settings():
    return Settings(
        _env_file=None, database_url=os.environ.get(
            "TEST_DATABASE_URL", "postgresql://foundit:foundit@localhost:5432/foundit_test"
        ), admin_key="a" * 32, cors_origins=["https://staff.example"],
    )


@pytest.fixture
def pool():
    value = MagicMock()
    value.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(return_value=(1,))
    value.close = AsyncMock()
    return value


@pytest.fixture
async def database_url():
    from scripts.database import temporary_database, test_database_url
    from scripts.dbmate import dbmate

    async with temporary_database(test_database_url()) as url:
        await dbmate(url, "up")
        yield url


@pytest.fixture
async def db(database_url):
    import asyncpg

    conn = await asyncpg.connect(database_url, timeout=5, command_timeout=10)
    try:
        yield conn
    finally:
        await conn.close(timeout=5)


@pytest.fixture
async def api(settings, database_url):
    import httpx

    from app.main import create_app

    app = create_app(settings.model_copy(update={"database_url": database_url}))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            yield client
