from uuid import UUID, uuid4

from app.db.generated.matching import find_match_candidates
from tests.test_search import candidate


async def test_source_absence_and_nullable_candidate_sentinel_decode(db):
    assert await find_match_candidates(db, report_id=uuid4(), window_days=30) == []
    source = await candidate(db, type="lost")
    rows = await find_match_candidates(db, report_id=UUID(source), window_days=30)
    assert len(rows) == 1
    assert rows[0].id_ is None and rows[0].type is None and rows[0].category is None
