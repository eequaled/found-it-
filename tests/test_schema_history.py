from pathlib import Path
import re
from uuid import uuid4

import asyncpg
import pytest

from tests.schema_helpers import insert_claim, insert_report


@pytest.fixture(params=["report", "claim"])
async def history_target(request, db):
    report = await insert_report(db)
    if request.param == "report":
        return "report_status_history", "report_id", report["id"], "pending_review", "open"
    claim = await insert_claim(db, report["id"])
    return "claim_status_history", "claim_id", claim["id"], "pending", "withdrawn"


async def append(db, target, previous, following, actor="owner", note=None):
    table, key, identity, _, _ = target
    return await db.fetchrow(
        f"INSERT INTO {table} ({key}, from_status, to_status, actor, note) "
        "VALUES ($1,$2,$3,$4,$5) RETURNING *", identity, previous, following, actor, note,
    )


async def test_history_initial_unique_and_stable_timeline(db, history_target):
    target = history_target
    first = await append(db, target, None, target[3])
    second = await append(db, target, target[3], target[4], note="Owner requested change")
    assert first["id"] < second["id"]
    assert first["from_status"] is None and first["note"] is None
    assert second["actor"] == "owner" and second["created_at"].tzinfo is not None
    with pytest.raises(asyncpg.UniqueViolationError):
        await append(db, target, None, target[3])
    table, key, identity, _, _ = target
    rows = await db.fetch(f"SELECT id FROM {table} WHERE {key}=$1 ORDER BY id", identity)
    assert [row["id"] for row in rows] == [first["id"], second["id"]]


async def test_history_rejects_missing_parents_and_restricts_deletion(db, history_target):
    target = history_target
    orphan = (target[0], target[1], uuid4(), target[3], target[4])
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await append(db, orphan, None, target[3])
    await append(db, target, None, target[3])
    parent = "reports" if target[1] == "report_id" else "claims"
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await db.execute(f"DELETE FROM {parent} WHERE id=$1", target[2])


@pytest.mark.parametrize("note", ["", " \t\n", "x" * 1001])
async def test_history_note_checks(db, history_target, note):
    with pytest.raises(asyncpg.CheckViolationError):
        await append(db, history_target, None, history_target[3], note=note)


async def test_history_status_and_actor_checks(db, history_target):
    target = history_target
    with pytest.raises(asyncpg.CheckViolationError):
        await append(db, target, target[3], target[3])
    with pytest.raises(asyncpg.InvalidTextRepresentationError):
        await append(db, target, None, "invented-status")
    with pytest.raises(asyncpg.InvalidTextRepresentationError):
        await append(db, target, None, target[3], actor="intruder")
    with pytest.raises(asyncpg.NotNullViolationError):
        await append(db, target, None, None)


def test_application_sql_has_no_history_mutation_path():
    root = Path(__file__).resolve().parents[1] / "app/db/queries"
    mutation = re.compile(
        r"\b(?:UPDATE|DELETE\s+FROM|TRUNCATE(?:\s+TABLE)?)\s+"
        r"(?:report_status_history|claim_status_history)\b", re.IGNORECASE,
    )
    for path in root.glob("*.sql"):
        assert not mutation.search(path.read_text()), path
