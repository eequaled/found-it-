from app.db.generated.matching import find_match_candidates
from app.errors import DomainError


async def find_matches(pool, report_id, window_days):
    async with pool.acquire(timeout=2) as conn:
        rows = await find_match_candidates(conn, report_id=report_id, window_days=window_days)
    if not rows:
        raise DomainError("not_found", "Report not found", 404)
    return {"items": [row for row in rows if row.id_ is not None]}
