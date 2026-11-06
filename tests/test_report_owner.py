from uuid import UUID, uuid4

import asyncpg
import pytest

from app.db.generated import history
from tests.report_helpers import report_payload


@pytest.mark.parametrize("status", ["pending_review", "open", "rejected", "resolved", "removed"])
async def test_owner_can_track_all_statuses_without_token_echo(api, db, status):
    created = (await api.post("/reports", json=report_payload())).json()
    identity = UUID(created["id"])
    if status != "pending_review":
        await db.execute("UPDATE reports SET status=$2 WHERE id=$1", identity, status)
        await db.execute("""INSERT INTO report_status_history (report_id,from_status,to_status,actor,note)
                          VALUES ($1,'pending_review',$2,'admin','Owner-visible note')""", identity, status)
    response = await api.get(f"/reports/{identity}/status", headers={"X-Tracking-Token": created["tracking_token"]})
    assert response.status_code == 200 and response.json()["status"] == status
    assert response.headers["cache-control"] == "no-store"
    assert set(response.json()) == {"id", "status", "history"}
    assert response.json()["history"][0]["from_status"] is None
    if status != "pending_review":
        assert response.json()["history"][-1]["note"] == "Owner-visible note"
    assert created["tracking_token"] not in response.text and "tracking_token_hash" not in response.text


@pytest.mark.parametrize("token", [None, "", "wrong", "x" * 129])
async def test_wrong_missing_or_other_report_tokens_return_identical_404(api, token):
    created = (await api.post("/reports", json=report_payload())).json()
    headers = {"X-Tracking-Token": token} if token is not None else {}
    denied = await api.get(f"/reports/{created['id']}/status", headers=headers)
    absent = await api.get(f"/reports/{uuid4()}/status", headers=headers)
    assert denied.status_code == absent.status_code == 404 and denied.json() == absent.json()
    assert denied.headers["cache-control"] == absent.headers["cache-control"] == "no-store"
    other = (await api.post("/reports", json=report_payload())).json()
    assert (await api.get(f"/reports/{other['id']}/status", headers={"X-Tracking-Token": created["tracking_token"]})).status_code == 404


async def test_owner_status_and_history_share_one_snapshot(api, database_url, monkeypatch):
    created = (await api.post("/reports", json=report_payload())).json()
    identity = UUID(created["id"])
    original = history.get_report_history

    async def concurrent_change(conn, *, report_id):
        external = await asyncpg.connect(database_url, timeout=5)
        try:
            async with external.transaction():
                await external.execute("UPDATE reports SET status='open' WHERE id=$1", identity)
                await external.execute("""INSERT INTO report_status_history (report_id,from_status,to_status,actor,note)
                                        VALUES ($1,'pending_review','open','admin','Accepted')""", identity)
        finally:
            await external.close()
        return await original(conn, report_id=report_id)

    monkeypatch.setattr("app.services.reports.history.get_report_history", concurrent_change)
    headers = {"X-Tracking-Token": created["tracking_token"]}
    response = await api.get(f"/reports/{identity}/status", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "pending_review" and len(response.json()["history"]) == 1
    monkeypatch.setattr("app.services.reports.history.get_report_history", original)
    later = (await api.get(f"/reports/{identity}/status", headers=headers)).json()
    assert later["status"] == "open" and len(later["history"]) == 2
