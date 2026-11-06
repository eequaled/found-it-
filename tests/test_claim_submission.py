import asyncio
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.security import issue_token, token_hash
from tests.test_search import candidate


def payload(**changes):
    return {"claimant_name": "Claimant", "claimant_contact": "private-owner@example.com",
            "evidence": "Private initials engraved inside the case", **changes}


async def submit(api, report, **changes):
    return await api.post(f"/reports/{report}/claims", json=payload(**changes))


async def test_claim_and_initial_history_commit_with_only_hash_stored(api, db):
    report = await candidate(db)
    response = await submit(api, report, claimant_name="  Claimant  ")
    assert response.status_code == 201 and response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {"id", "tracking_token"} and len(body["tracking_token"]) == 43
    row = await db.fetchrow("SELECT * FROM claims WHERE id=$1", UUID(body["id"]))
    assert row["status"] == "pending" and row["report_id"] == UUID(report)
    assert row["claimant_name"] == "Claimant" and row["tracking_token_hash"] == token_hash(body["tracking_token"])
    assert row["evidence"] == payload()["evidence"] and row["decided_at"] is None
    event = await db.fetchrow("SELECT * FROM claim_status_history WHERE claim_id=$1", row["id"])
    assert event["from_status"] is None and event["to_status"] == "pending" and event["actor"] == "owner"
    for path in (f"/reports/{report}", "/reports", f"/reports/{report}/matches"):
        public = await api.get(path)
        assert payload()["claimant_contact"] not in public.text and payload()["evidence"] not in public.text
        assert body["tracking_token"] not in public.text


@pytest.mark.parametrize("kind,status", [("lost", "open"), ("found", "pending_review"), ("found", "rejected"),
                                         ("found", "resolved"), ("found", "removed")])
async def test_wrong_type_or_state_is_conflict_without_writes(api, db, kind, status):
    response = await submit(api, await candidate(db, type=kind, status=status))
    assert response.status_code == 409 and response.json()["error"]["code"] == "claim_not_allowed"
    assert await db.fetchval("SELECT count(*) FROM claims") == 0
    assert await db.fetchval("SELECT count(*) FROM claim_status_history") == 0


async def test_missing_report_and_invalid_uuid(api, db):
    assert (await submit(api, uuid4())).status_code == 404
    assert (await submit(api, "not-a-uuid")).status_code == 422
    assert await db.fetchval("SELECT count(*) FROM claims") == 0


@pytest.mark.parametrize("changes", [{"claimant_name": " "}, {"claimant_name": "x" * 101},
    {"claimant_contact": " "}, {"claimant_contact": "x" * 255}, {"evidence": "short"},
    {"evidence": "x" * 5001}, {"status": "approved"}, {"tracking_token_hash": "private-secret"}, {"report_id": str(uuid4())}])
async def test_invalid_claim_fields_are_422_without_echo_or_writes(api, db, changes):
    response = await submit(api, await candidate(db), **changes)
    assert response.status_code == 422 and response.json()["error"]["code"] == "validation_error"
    assert "private-secret" not in response.text
    assert await db.fetchval("SELECT count(*) FROM claims") == 0


@pytest.mark.parametrize("field", ["claimant_name", "claimant_contact", "evidence"])
async def test_required_fields_cannot_be_omitted(api, db, field):
    body = payload()
    del body[field]
    response = await api.post(f"/reports/{await candidate(db)}/claims", json=body)
    assert response.status_code == 422
    assert await db.fetchval("SELECT count(*) FROM claims") == 0


@pytest.mark.parametrize("failure", [RuntimeError("private SQL failure"), None])
async def test_history_failure_rolls_back_claim_and_never_delivers_token(api, db, monkeypatch, failure):
    fake = AsyncMock(side_effect=failure) if failure else AsyncMock(return_value=None)
    monkeypatch.setattr("app.services.claims.history.insert_claim_history", fake)
    response = await submit(api, await candidate(db))
    assert response.status_code == 500 and response.headers["cache-control"] == "no-store"
    assert "private SQL" not in response.text and "tracking_token" not in response.text
    assert await db.fetchval("SELECT count(*) FROM claims") == 0
    assert await db.fetchval("SELECT count(*) FROM claim_status_history") == 0


async def test_token_collision_rolls_back_only_second_claim(api, db, monkeypatch):
    raw, digest = issue_token()
    monkeypatch.setattr("app.services.claims.issue_token", lambda: (raw, digest))
    report = await candidate(db)
    assert (await submit(api, report)).status_code == 201
    response = await submit(api, report)
    assert response.status_code == 409 and raw not in response.text
    assert await db.fetchval("SELECT count(*) FROM claims") == 1
    assert await db.fetchval("SELECT count(*) FROM claim_status_history") == 1


async def test_concurrent_submissions_share_report_lock_and_all_remain_pending(api, db, monkeypatch):
    from app.db.generated import claims

    report, ready, reached = await candidate(db), asyncio.Event(), 0
    original = claims.lock_report_for_claim

    async def barrier(conn, **kwargs):
        nonlocal reached
        row = await original(conn, **kwargs)
        reached += 1
        if reached == 6:
            ready.set()
        await asyncio.wait_for(ready.wait(), 5)
        return row

    monkeypatch.setattr(claims, "lock_report_for_claim", barrier)
    responses = await asyncio.gather(*(submit(api, report) for _ in range(6)))
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()["tracking_token"] for response in responses}) == 6
    assert await db.fetchval("SELECT count(*) FROM claims WHERE status='pending'") == 6
    assert await db.fetchval("SELECT count(*) FROM claim_status_history") == 6
    assert await db.fetchval("SELECT status FROM reports") == "open"


async def test_transport_cap_applies_to_chunked_claim_body(api, db):
    report = await candidate(db)

    async def chunks():
        yield b"x" * 40000
        yield b"x" * 40000

    response = await api.post(f"/reports/{report}/claims", content=chunks(), headers={"Content-Type": "application/json"})
    assert response.status_code == 413 and response.headers["cache-control"] == "no-store"
    assert await db.fetchval("SELECT count(*) FROM claims") == 0
