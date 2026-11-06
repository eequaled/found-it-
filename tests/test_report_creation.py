from unittest.mock import AsyncMock

import pytest

from app.security import issue_token, token_hash
from tests.report_helpers import report_payload


@pytest.mark.parametrize("kind", ["lost", "found"])
async def test_create_report_commits_only_hash_and_initial_history(api, db, kind):
    response = await api.post("/reports", json=report_payload(type=kind, contact_email="owner@example.com"))
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {"id", "tracking_token"}
    assert len(body["tracking_token"]) == 43
    row = await db.fetchrow("SELECT * FROM reports WHERE id=$1::text::uuid", body["id"])
    assert row["type"] == kind and row["status"] == "pending_review"
    assert row["tracking_token_hash"] == token_hash(body["tracking_token"])
    assert row["contact_email"] == "owner@example.com"
    events = await db.fetch("SELECT * FROM report_status_history WHERE report_id=$1", row["id"])
    assert len(events) == 1 and events[0]["from_status"] is None
    assert events[0]["to_status"] == "pending_review" and events[0]["actor"] == "owner"


@pytest.mark.parametrize("field", ["type", "category", "title", "description", "event_date", "location_text"])
async def test_missing_required_fields_return_422_without_writes(api, db, field):
    body = report_payload()
    del body[field]
    response = await api.post("/reports", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body." + field
    assert await db.fetchval("SELECT count(*) FROM reports") == 0


@pytest.mark.parametrize("failure", [RuntimeError("INSERT private_sql"), None])
async def test_history_failure_rolls_back_report_and_never_returns_token(api, db, monkeypatch, failure):
    fake = AsyncMock(side_effect=failure) if failure else AsyncMock(return_value=None)
    monkeypatch.setattr("app.services.reports.history.insert_report_history", fake)
    response = await api.post("/reports", json=report_payload())
    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "internal_error"
    assert "private_sql" not in response.text and "tracking_token" not in response.text
    assert await db.fetchval("SELECT count(*) FROM reports") == 0
    assert await db.fetchval("SELECT count(*) FROM report_status_history") == 0


async def test_token_hash_collision_rolls_back_the_second_create(api, db, monkeypatch):
    raw, digest = issue_token()
    monkeypatch.setattr("app.services.reports.issue_token", lambda: (raw, digest))
    assert (await api.post("/reports", json=report_payload())).status_code == 201
    response = await api.post("/reports", json=report_payload())
    assert response.status_code == 409 and raw not in response.text
    assert await db.fetchval("SELECT count(*) FROM reports") == 1
    assert await db.fetchval("SELECT count(*) FROM report_status_history") == 1


async def test_invalid_fields_are_reported_together_without_echoing_input(api, db):
    body = report_payload(title=" ", category="invented", contact_email="private-invalid-email", status="open")
    response = await api.post("/reports", json=body)
    assert response.status_code == 422
    fields = {item["field"] for item in response.json()["error"]["details"]}
    assert fields == {"body.title", "body.category", "body.contact_email", "body.status"}
    assert "private-invalid-email" not in response.text
    assert await db.fetchval("SELECT count(*) FROM reports") == 0
