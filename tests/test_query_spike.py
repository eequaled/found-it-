from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

import asyncpg
import pytest

from app.db.generated import enums, history, reports
from tests.schema_helpers import insert_claim, insert_report


@pytest.fixture
async def query_pool(database_url):
    async with asyncpg.create_pool(
        database_url, min_size=1, max_size=2, timeout=5, command_timeout=10,
    ) as pool:
        yield pool


def report_values():
    return dict(
        type=enums.ReportType.FOUND, category=enums.ReportCategory.PHONE,
        title="هاتف téléphone phone", description="Black phone with a distinctive case",
        event_date=datetime.now(UTC).date(), location_text="Central station",
        contact_name=None, contact_email=None, contact_phone=None, photo_path=None,
        tracking_token_hash=memoryview(sha256(uuid4().bytes).digest()),
    )


async def test_generated_report_roundtrip_through_pool(query_pool):
    values = report_values()
    async with query_pool.acquire() as conn:
        row = await reports.insert_report(conn, **values)
        assert row is not None
        assert row.type is enums.ReportType.FOUND
        assert row.status is enums.ReportStatus.PENDING_REVIEW
        assert row.category is enums.ReportCategory.PHONE
        assert isinstance(row.tracking_token_hash, memoryview)
        assert bytes(row.tracking_token_hash) == bytes(values["tracking_token_hash"])
        assert row.contact_email is None and row.photo_path is None
        assert "téléphone" in row.search_vector and row.created_at.tzinfo is not None
        assert await reports.get_report_by_id(conn, id_=row.id_) == row
        assert await reports.get_report_by_id(conn, id_=uuid4()) is None


async def test_generated_report_history_await_and_cursor(query_pool):
    async with query_pool.acquire() as conn, conn.transaction():
        report = await reports.insert_report(conn, **report_values())
        initial = await history.insert_report_history(
            conn, report_id=report.id_, from_status=None,
            to_status=enums.ReportStatus.PENDING_REVIEW, actor=enums.StatusActor.OWNER, note=None,
        )
        approved = await history.insert_report_history(
            conn, report_id=report.id_, from_status=enums.ReportStatus.PENDING_REVIEW,
            to_status=enums.ReportStatus.OPEN, actor=enums.StatusActor.ADMIN, note="Accepted",
        )
        events = await history.get_report_history(conn, report_id=report.id_)
        streamed = [event async for event in history.get_report_history(conn, report_id=report.id_)]
        assert events == streamed
        assert [event.id_ for event in events] == [initial.id_, approved.id_]
        assert events[0].from_status is None and events[0].note is None
        assert events[1].from_status is enums.ReportStatus.PENDING_REVIEW
        assert events[1].actor is enums.StatusActor.ADMIN
        assert await history.get_report_history(conn, report_id=uuid4()) == []


async def test_generated_report_and_history_rollback_together(query_pool):
    async with query_pool.acquire() as conn:
        with pytest.raises(asyncpg.CheckViolationError):
            async with conn.transaction():
                report = await reports.insert_report(conn, **report_values())
                await history.insert_report_history(
                    conn, report_id=report.id_, from_status=None,
                    to_status=enums.ReportStatus.PENDING_REVIEW, actor=enums.StatusActor.OWNER, note="",
                )
        assert await reports.get_report_by_id(conn, id_=report.id_) is None
        assert await history.get_report_history(conn, report_id=report.id_) == []


async def test_generated_claim_history_roundtrip(query_pool):
    async with query_pool.acquire() as conn:
        report = await insert_report(conn)
        claim = await insert_claim(conn, report["id"])
        first = await history.insert_claim_history(
            conn, claim_id=claim["id"], from_status=None,
            to_status=enums.ClaimStatus.PENDING, actor=enums.StatusActor.OWNER, note=None,
        )
        second = await history.insert_claim_history(
            conn, claim_id=claim["id"], from_status=enums.ClaimStatus.PENDING,
            to_status=enums.ClaimStatus.WITHDRAWN, actor=enums.StatusActor.OWNER, note=None,
        )
        events = await history.get_claim_history(conn, claim_id=claim["id"])
        assert [event.id_ for event in events] == [first.id_, second.id_]
        assert events[1].to_status is enums.ClaimStatus.WITHDRAWN
        assert events[0].from_status is None
        assert await history.get_claim_history(conn, claim_id=uuid4()) == []
