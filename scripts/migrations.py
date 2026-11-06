"""Rollback verification always runs against a new disposable database."""
import asyncio

import asyncpg

from scripts.database import temporary_database, test_database_url
from scripts.dbmate import dbmate


async def check_migrations():
    async with temporary_database(test_database_url()) as url:
        await dbmate(url, "up")
        conn = await asyncpg.connect(url, timeout=5, command_timeout=10)
        try:
            query = "SELECT version FROM schema_migrations ORDER BY version"
            versions = await conn.fetch(query)
            for index in range(len(versions)):
                await dbmate(url, "rollback")
                assert await conn.fetch(query) == versions[:len(versions) - index - 1]
            assert not await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                "AND tablename <> 'schema_migrations'"
            ), "Rollback left application tables behind"
            assert not await conn.fetch(
                "SELECT typname FROM pg_type WHERE typtype='e' "
                "AND typnamespace='public'::regnamespace"
            ), "Rollback left application enums behind"
            assert not await conn.fetchval(
                "SELECT 1 FROM pg_extension WHERE extname='pg_trgm'"
            ), "Rollback left the application trigram extension behind"
            await dbmate(url, "up")
            assert await conn.fetch(query) == versions
        finally:
            await conn.close(timeout=5)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["check"]:
        asyncio.run(check_migrations())
    elif sys.argv[1:] in (["up"], ["rollback"]):
        from app.config import Settings
        asyncio.run(dbmate(str(Settings().database_url), sys.argv[1]))
    else:
        raise SystemExit("usage: python -m scripts.migrations up|rollback|check")
