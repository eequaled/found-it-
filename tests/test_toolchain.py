"""Exercise the generated asyncpg adapter against an isolated migrated database."""
import asyncpg

from app.db.generated.health import health_probe


async def test_generated_health_probe(database_url):
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
    try:
        async with pool.acquire() as connection:
            assert await health_probe(connection) == 1
    finally:
        await pool.close()
