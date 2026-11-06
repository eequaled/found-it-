from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest

from tests.schema_helpers import insert_claim
from tests.test_search import candidate


async def matches(api, source):
    response = await api.get(f"/reports/{source}/matches")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert set(response.json()) == {"items"}
    return response.json()["items"]


@pytest.mark.parametrize("kind,opposite", [("lost", "found"), ("found", "lost")])
async def test_candidates_require_opposite_type_same_category_open_and_date_window(api, db, kind, opposite):
    source = await candidate(db, type=kind)
    included = await candidate(db, type=opposite)
    await candidate(db, type=kind)
    await candidate(db, type=opposite, category="wallet")
    await candidate(db, type=opposite, status="pending_review")
    await candidate(db, type=opposite, day="2026-02-10")
    assert [row["id"] for row in await matches(api, source)] == [included]


@pytest.mark.parametrize("status", ["pending_review", "rejected", "removed", "resolved"])
async def test_nonpublic_source_and_missing_source_are_indistinguishable(api, db, status):
    source = await candidate(db, type="lost", status=status)
    await candidate(db)
    hidden = await api.get(f"/reports/{source}/matches")
    missing = await api.get(f"/reports/{uuid4()}/matches")
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()
    assert hidden.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("status", ["pending_review", "rejected", "removed", "resolved"])
async def test_nonpublic_candidates_never_appear(api, db, status):
    source = await candidate(db, type="lost")
    await candidate(db, status=status)
    assert await matches(api, source) == []


async def test_empty_list_and_missing_source_are_distinct_and_uuid_is_validated(api, db):
    source = await candidate(db, type="lost")
    assert await matches(api, source) == []
    assert (await api.get("/reports/not-a-uuid/matches")).status_code == 422


async def test_inclusive_date_bounds_and_configured_window(api, db):
    source = await candidate(db, type="lost")
    origin = date(2026, 1, 10)
    boundary = [await candidate(db, day=(origin + timedelta(days=days)).isoformat()) for days in (-30, 30)]
    await candidate(db, day=(origin - timedelta(days=31)).isoformat())
    await candidate(db, day=(origin + timedelta(days=31)).isoformat())
    assert {row["id"] for row in await matches(api, source)} == set(boundary)
    api._transport.app.state.settings.match_window_days = 1
    assert await matches(api, source) == []
    near = await candidate(db, day="2026-01-11")
    assert [row["id"] for row in await matches(api, source)] == [near]


@pytest.mark.parametrize("signal", ["text", "location", "date"])
async def test_each_scoring_signal_can_outweigh_recency(api, db, signal):
    source = await candidate(db, type="lost")
    best = await candidate(db)
    changes = {"text": {"title": "Leather wallet", "description": "Brown leather with many compartments"},
               "location": {"location_text": "Remote airport terminal"}, "date": {"day": "2026-01-11"}}[signal]
    newer = await candidate(db, created="2026-02-01T00:00:00+00:00", **changes)
    assert [row["id"] for row in await matches(api, source)] == [best, newer]


async def test_ties_use_newest_then_uuid_and_list_is_bounded_to_ten_public_items(api, db):
    source = await candidate(db, type="lost")
    ids = [await candidate(db, contact_email="private-owner@example.com") for _ in range(12)]
    items = await matches(api, source)
    assert [row["id"] for row in items] == sorted(ids, reverse=True)[:10]
    assert items == await matches(api, source)
    for item in items:
        assert set(item) == {"id", "type", "category", "title", "description", "event_date", "location_text", "created_at"}
        assert "private-owner" not in str(item)
    newest = await candidate(db, created="2026-01-11T00:00:00+00:00")
    assert (await matches(api, source))[0]["id"] == newest
    assert len((await api.get(f"/reports/{source}/matches", params={"limit": 10000})).json()["items"]) == 10


async def test_suggestions_do_not_write_reports_claims_or_history(api, db):
    source = await candidate(db, type="lost")
    found = await candidate(db)
    await insert_claim(db, UUID(found))
    tables = ("reports", "claims", "report_status_history", "claim_status_history")
    before = [await db.fetch(f"SELECT * FROM {table} ORDER BY id") for table in tables]
    assert [row["id"] for row in await matches(api, source)] == [found]
    after = [await db.fetch(f"SELECT * FROM {table} ORDER BY id") for table in tables]
    assert after == before
