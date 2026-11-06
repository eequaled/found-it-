async def test_search_indexes_cover_actual_predicates_and_public_order(db):
    indexes = {row["indexname"]: row["indexdef"] for row in await db.fetch(
        "SELECT indexname,indexdef FROM pg_indexes WHERE tablename='reports'"
    )}
    assert "USING gin (search_vector)" in indexes["reports_search_gin"]
    assert "gin_trgm_ops" in indexes["reports_location_trgm"]
    assert "created_at DESC, id DESC" in indexes["reports_public_order"]
    assert all("WHERE (status = 'open'::report_status)" in indexes[name] for name in (
        "reports_search_gin", "reports_location_trgm", "reports_public_order",
    ))
