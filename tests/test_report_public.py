from dataclasses import asdict
from uuid import UUID, uuid4

import pytest

from app.db.generated import reports
from tests.report_helpers import report_payload


async def test_public_report_uses_only_public_columns_and_response_fields(api, db):
    created = (await api.post("/reports", json=report_payload(
        contact_name="PrivateOwner", contact_email="private@example.com", contact_phone="+213 555 123 456",
    ))).json()
    identity = UUID(created["id"])
    await db.execute("UPDATE reports SET status='open' WHERE id=$1", identity)
    await db.execute("""INSERT INTO report_status_history (report_id, from_status, to_status, actor, note)
                      VALUES ($1,'pending_review','open','admin','Private moderation note')""", identity)
    response = await api.get(f"/reports/{identity}")
    expected = {"id", "type", "category", "title", "description", "event_date", "location_text", "created_at"}
    assert response.status_code == 200 and set(response.json()) == expected
    assert response.headers["cache-control"] == "no-store"
    for secret in ["PrivateOwner", "private@example.com", "+213", "Private moderation note", created["tracking_token"]]:
        assert secret not in response.text
    row = await reports.get_public_report(db, id_=identity)
    assert set(asdict(row)) == (expected - {"id"}) | {"id_"}


@pytest.mark.parametrize("status", ["pending_review", "resolved", "rejected", "removed"])
async def test_non_public_reports_are_indistinguishable_from_missing(api, db, status):
    created = (await api.post("/reports", json=report_payload())).json()
    identity = UUID(created["id"])
    await db.execute("UPDATE reports SET status=$2 WHERE id=$1", identity, status)
    hidden = await api.get(f"/reports/{identity}")
    absent = await api.get(f"/reports/{uuid4()}")
    assert hidden.status_code == absent.status_code == 404
    assert hidden.json() == absent.json()
