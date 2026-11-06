import pytest

from app.db.generated.search import search_public_reports
from tests.schema_helpers import insert_report


@pytest.mark.parametrize("has_row", [False, True])
async def test_empty_page_still_decodes_one_count_row_with_nullable_sentinel(db, has_row):
    if has_row:
        await insert_report(db)
        await db.execute("UPDATE reports SET status='open'")
    rows = await search_public_reports(
        db, q=None, type=None, category=None, date_from=None, date_to=None,
        location_pattern=None, page_size=2, page_offset=10,
    )
    assert len(rows) == 1 and rows[0].total == int(has_row)
    assert rows[0].id_ is None and rows[0].type is None and rows[0].category is None
