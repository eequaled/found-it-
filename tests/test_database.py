import os
from pathlib import Path
from urllib.parse import urlsplit

import asyncpg
import pytest

from scripts.database import temporary_database


async def test_fixture_applies_every_migration(database_url, db):
    assert (await db.fetchval("SELECT current_database()")).startswith("foundit_test_")
    expected = len(list((Path(__file__).resolve().parents[1] / "migrations").glob("*.sql")))
    assert await db.fetchval("SELECT count(*) FROM schema_migrations") == expected
    assert urlsplit(database_url).query == urlsplit(os.environ["TEST_DATABASE_URL"]).query


async def test_databases_are_isolated_and_cleanup_after_failure(database_url, db):
    name = None
    with pytest.raises(RuntimeError, match="intentional test failure"):
        async with temporary_database(os.environ["TEST_DATABASE_URL"]) as other:
            name = urlsplit(other).path[1:]
            conn = await asyncpg.connect(other, timeout=5)
            try:
                await conn.execute("CREATE TABLE isolation_probe (value integer)")
                assert await db.fetchval("SELECT to_regclass('public.isolation_probe')") is None
                assert other != database_url
            finally:
                await conn.close()
            raise RuntimeError("intentional test failure")
    assert await db.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", name) is None


async def test_api_uses_migrated_database(api):
    response = await api.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
