async def test_match_index_supports_type_category_equality_and_date_range(db):
    definition = await db.fetchval("SELECT indexdef FROM pg_indexes WHERE indexname='reports_match_candidates'")
    assert "(type, category, event_date)" in definition
    assert "WHERE (status = 'open'::report_status)" in definition
