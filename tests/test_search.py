from datetime import date, datetime

import pytest

from tests.schema_helpers import insert_report


async def candidate(db, *, status="open", day="2026-01-10", created="2026-01-10T12:00:00+00:00", **values):
    row = await insert_report(db, **values)
    await db.execute("UPDATE reports SET status=$1,event_date=$2,created_at=$3 WHERE id=$4",
                     status, date.fromisoformat(day), datetime.fromisoformat(created), row["id"])
    return str(row["id"])


@pytest.mark.parametrize("status", ["pending_review", "rejected", "resolved", "removed"])
async def test_search_only_returns_open_reports_and_public_columns(api, db, status):
    public_id = await candidate(db, contact_email="owner-secret@example.com")
    await candidate(db, status=status, contact_name="Private owner")
    for params in ({}, {"q": "phone"}):
        response = await api.get("/reports", params=params)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        body = response.json()
        assert set(body) == {"items", "total", "page", "page_size"}
        assert body["total"] == 1 and body["items"][0]["id"] == public_id
        assert set(body["items"][0]) == {"id", "type", "category", "title", "description", "event_date", "location_text", "created_at"}
        assert "owner-secret" not in response.text and "Private owner" not in response.text


async def test_keyword_matches_title_or_description_and_orders_by_rank_before_recency(api, db):
    title = await candidate(db, title="Phone", description="A distinctive red item", created="2026-01-01T00:00:00+00:00")
    description = await candidate(db, title="Found item", description="A distinctive red phone", created="2026-02-01T00:00:00+00:00")
    await candidate(db, title="Wallet", description="Leather wallet with initials")
    body = (await api.get("/reports", params={"q": "phone"})).json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [title, description]


@pytest.mark.parametrize("title,query", [("Téléphone rouge", "téléphone"), ("هاتف أسود", "هاتف")])
async def test_simple_search_supports_french_and_arabic(api, db, title, query):
    match = await candidate(db, title=title)
    body = (await api.get("/reports", params={"q": query})).json()
    assert body["total"] == 1 and body["items"][0]["id"] == match


async def test_all_filters_are_combined_with_inclusive_date_bounds(api, db):
    match = await candidate(db, type="lost", day="2026-01-10", location_text="North CENTRAL Station")
    await candidate(db, type="found", day="2026-01-10", location_text="North CENTRAL Station")
    await candidate(db, type="lost", day="2026-01-09", location_text="North CENTRAL Station")
    await candidate(db, type="lost", category="wallet", location_text="North CENTRAL Station")
    await candidate(db, type="lost", location_text="South bus terminal")
    body = (await api.get("/reports", params={"q": "phone", "type": "lost", "category": "phone",
                                             "date_from": "2026-01-10", "date_to": "2026-01-10", "location": "central"})).json()
    assert body["total"] == 1 and body["items"][0]["id"] == match


@pytest.mark.parametrize("literal", ["%", "_", "\\"])
async def test_location_treats_sql_wildcards_and_escape_as_literal_characters(api, db, literal):
    match = await candidate(db, location_text="Passage " + literal + " North")
    await candidate(db, location_text="Passage ordinary North")
    body = (await api.get("/reports", params={"location": literal})).json()
    assert body["total"] == 1 and body["items"][0]["id"] == match


async def test_stable_pages_use_newest_then_id_and_keep_exact_total_past_last_page(api, db):
    ids = [await candidate(db) for _ in range(5)]
    expected = sorted(ids, reverse=True)
    for page, wanted in [(1, expected[:2]), (2, expected[2:4]), (3, expected[4:]), (4, [])]:
        params = {"page": page, "page_size": 2}
        first = (await api.get("/reports", params=params)).json()
        second = (await api.get("/reports", params=params)).json()
        assert first == second
        assert first["total"] == 5 and first["page"] == page and first["page_size"] == 2
        assert [item["id"] for item in first["items"]] == wanted
    newest = await candidate(db, created="2026-01-11T00:00:00+00:00")
    assert (await api.get("/reports", params={"page_size": 1})).json()["items"][0]["id"] == newest


async def test_empty_filters_blank_query_and_empty_database_are_well_defined(api, db):
    assert (await api.get("/reports", params={"page": 99})).json() == {"items": [], "total": 0, "page": 99, "page_size": 20}
    await candidate(db)
    assert (await api.get("/reports", params={"q": "missingword"})).json()["total"] == 0
    assert (await api.get("/reports", params={"q": "   ", "location": "   "})).json()["total"] == 1
    assert (await api.get("/reports", params={"q": "!!!"})).json()["total"] == 0


@pytest.mark.parametrize("params", [
    {"page": 0}, {"page": 1_000_001}, {"page_size": 0}, {"page_size": 101}, {"page_size": 201},
    {"page_size": "1.5"}, {"q": "x" * 201}, {"location": "x" * 201}, {"type": "other"}, {"category": "invented"},
    {"date_from": "2026-1-1"}, {"date_to": "2026-02-30"}, {"date_to": "2026-01-01T00:00:00Z"},
    {"date_from": "0"}, {"date_from": "2026-02-01", "date_to": "2026-01-01"}, {"status": "pending_review"},
])
async def test_invalid_search_parameters_use_422_without_echoing_input(api, params):
    response = await api.get("/reports", params=params)
    assert response.status_code == 422 and response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "validation_error"
    assert all(item["field"].startswith("query") for item in response.json()["error"]["details"])


async def test_runtime_pagination_defaults_and_maximum_are_honored(api):
    settings = api._transport.app.state.settings
    settings.default_page_size, settings.max_page_size = 1, 2
    assert (await api.get("/reports")).json()["page_size"] == 1
    assert (await api.get("/reports", params={"page_size": 2})).status_code == 200
    assert (await api.get("/reports", params={"page_size": 3})).status_code == 422


async def test_search_is_read_only_and_websearch_input_is_parameterized(api, db):
    await candidate(db)
    before = await db.fetchrow("SELECT count(*) AS n, max(updated_at) AS updated FROM reports")
    assert (await api.get("/reports", params={"q": "' OR 1=1; --"})).status_code == 200
    assert await db.fetchrow("SELECT count(*) AS n, max(updated_at) AS updated FROM reports") == before
    assert await db.fetchval("SELECT count(*) FROM claims") == 0
    assert await db.fetchval("SELECT count(*) FROM report_status_history") == 0
