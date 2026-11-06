import asyncio
from uuid import uuid4

import asyncpg
import pytest

from tests.schema_helpers import insert_claim, insert_report


async def test_claim_defaults_and_found_only_foreign_key(db):
    found = await insert_report(db)
    claim = await insert_claim(db, found["id"])
    assert claim["status"] == "pending"
    assert claim["decided_at"] is None and claim["decision_note"] is None
    lost = await insert_report(db, type="lost")
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await insert_claim(db, lost["id"])
    with pytest.raises(asyncpg.CheckViolationError):
        await insert_claim(db, lost["id"], report_type="lost")
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await insert_claim(db, uuid4())
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await db.execute("DELETE FROM reports WHERE id=$1", found["id"])


@pytest.mark.parametrize("changes", [
    {"claimant_name": ""}, {"claimant_name": "x" * 101},
    {"claimant_contact": "  "}, {"claimant_contact": "x" * 255},
    {"evidence": "short"}, {"evidence": "x" * 5001}, {"evidence": " " * 10},
    {"tracking_token_hash": b"short"},
])
async def test_claim_checks_cannot_be_bypassed(db, changes):
    found = await insert_report(db)
    with pytest.raises(asyncpg.CheckViolationError):
        await insert_claim(db, found["id"], **changes)


async def test_claim_token_uniqueness_and_decision_consistency(db):
    found = await insert_report(db)
    claim = await insert_claim(db, found["id"])
    with pytest.raises(asyncpg.UniqueViolationError):
        await insert_claim(db, found["id"], tracking_token_hash=claim["tracking_token_hash"])
    for assignment in ["status='approved'", "decision_note='premature note'",
                       "status='rejected', decided_at=now()",
                       "status='withdrawn', decided_at=now(), decision_note=' '"]:
        with pytest.raises(asyncpg.CheckViolationError):
            await db.execute(f"UPDATE claims SET {assignment} WHERE id=$1", claim["id"])
    await db.execute("""UPDATE claims SET status='rejected', decided_at=now(),
                     decision_note='Insufficient evidence' WHERE id=$1""", claim["id"])
    await insert_claim(db, found["id"])


async def test_one_approval_index_survives_concurrent_direct_updates(db, database_url):
    found = await insert_report(db)
    claims = [await insert_claim(db, found["id"]) for _ in range(4)]

    async def approve(claim_id):
        conn = await asyncpg.connect(database_url, timeout=5, command_timeout=10)
        try:
            return await conn.execute(
                "UPDATE claims SET status='approved', decided_at=now() WHERE id=$1", claim_id,
            )
        finally:
            await conn.close()

    results = await asyncio.gather(*(approve(c["id"]) for c in claims), return_exceptions=True)
    assert results.count("UPDATE 1") == 1
    assert sum(isinstance(r, asyncpg.UniqueViolationError) for r in results) == 3
    assert await db.fetchval("SELECT count(*) FROM claims WHERE status='approved'") == 1
    other = await insert_report(db)
    other_claim = await insert_claim(db, other["id"])
    await db.execute("UPDATE claims SET status='approved', decided_at=now() WHERE id=$1", other_claim["id"])
