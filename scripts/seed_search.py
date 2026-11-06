"""Synthetic query-plan fixture, only in a newly owned disposable database."""
import argparse
import asyncio
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import asyncpg

from scripts.database import temporary_database, test_database_url
from scripts.dbmate import dbmate

SEED = """
WITH seeded AS (
    INSERT INTO reports (type, status, category, title, description, event_date,
                         location_text, tracking_token_hash, created_at)
    SELECT (CASE WHEN n % 2 = 0 THEN 'lost' ELSE 'found' END)::report_type,
           (CASE WHEN n % 10 < 7 THEN 'open' WHEN n % 10 < 9 THEN 'pending_review'
                 ELSE 'resolved' END)::report_status,
           (ARRAY['phone','wallet','keys','bag','documents','clothing','other'])[1+n%7]::report_category,
           (ARRAY['Black phone','Leather wallet','Spare keys','Blue backpack',
                  'Identity documents','Winter jacket','Other item'])[1+n%7],
           format('Synthetic report %s: distinctive case or initials. %s', n,
                  (ARRAY['Téléphone retrouvé','هاتف أسود','Found near a station'])[1+n%3]),
           CURRENT_DATE - (n % 180),
           (ARRAY['Central station','University library','North market','Airport terminal'])[1+n%4],
           decode(replace(gen_random_uuid()::text,'-','') || replace(gen_random_uuid()::text,'-',''), 'hex'),
           now() - (n % 10000) * interval '1 minute'
    FROM generate_series(1, $1::int) AS series(n)
    RETURNING id, status, created_at
)
INSERT INTO report_status_history (report_id, to_status, actor, note, created_at)
SELECT id, status, 'system', 'Synthetic query-plan fixture, not an actual moderation event', created_at FROM seeded
"""


@asynccontextmanager
async def search_dataset(base_url: str, rows: int = 100_000):
    if not 1 <= rows <= 1_000_000:
        raise ValueError("Seed size must be between 1 and 1000000")
    async with temporary_database(base_url) as url:
        await dbmate(url, "up")
        conn = await asyncpg.connect(url, timeout=5, command_timeout=120)
        try:
            await conn.execute(SEED, rows)
            await conn.execute("ANALYZE reports")
        finally:
            await conn.close(timeout=5)
        yield url


async def main(rows):
    async with search_dataset(test_database_url(), rows) as url:
        # Print only the database name, never credentials from the URL.
        print(f"Ready: {rows} synthetic reports in {urlsplit(url).path[1:]}", flush=True)
        print("Use the test server credentials in another terminal; Ctrl-C drops this owned database.", flush=True)
        await asyncio.Event().wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100_000)
    asyncio.run(main(parser.parse_args().rows))
