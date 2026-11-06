from urllib.parse import urlsplit

import asyncpg
import pytest

from scripts.seed_search import search_dataset


async def test_seed_isolated_rows_history_search_vectors_and_cleanup(database_url):
    async with search_dataset(database_url, 70) as url:
        name = urlsplit(url).path[1:]
        conn = await asyncpg.connect(url)
        try:
            assert await conn.fetchval("SELECT count(*) FROM reports") == 70
            assert await conn.fetchval("SELECT count(DISTINCT category) FROM reports") == 7
            assert await conn.fetchval("SELECT count(DISTINCT type) FROM reports") == 2
            assert await conn.fetchval("SELECT count(*) FROM report_status_history") == 70
            assert await conn.fetchval("SELECT count(*) FROM reports WHERE search_vector @@ to_tsquery('simple','phone')") > 0
        finally:
            await conn.close()
    admin = await asyncpg.connect(database_url)
    try:
        assert not await admin.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", name)
        assert await admin.fetchval("SELECT count(*) FROM reports") == 0
    finally:
        await admin.close()


@pytest.mark.parametrize("rows", [0, 1_000_001])
async def test_invalid_seed_size_fails_before_connecting(rows):
    with pytest.raises(ValueError):
        async with search_dataset("not a database URL", rows):
            pytest.fail("must not connect")
