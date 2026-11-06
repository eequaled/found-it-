"""Exercise the generated asyncpg adapter against the CI PostgreSQL service."""
import os

import asyncpg

from app.db.generated.health import health_probe


async def test_generated_health_probe():
    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    try:
        async with pool.acquire() as connection:
            assert await health_probe(connection) == 1
    finally:
        await pool.close()
