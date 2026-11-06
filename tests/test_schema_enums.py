import asyncpg
import pytest


async def test_enums_and_trigram_extension(db):
    expected = {
        "report_type": ["lost", "found"],
        "report_status": ["pending_review", "open", "resolved", "rejected", "removed"],
        "claim_status": ["pending", "approved", "rejected", "withdrawn"],
        "report_category": ["phone", "wallet", "keys", "bag", "documents", "clothing", "other"],
        "status_actor": ["system", "owner", "admin"],
    }
    for name, labels in expected.items():
        actual = await db.fetch("""
            SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
            WHERE t.typname=$1 ORDER BY e.enumsortorder
        """, name)
        assert [row["enumlabel"] for row in actual] == labels
    assert await db.fetchval("SELECT similarity('found phone', 'found phone')") == 1


@pytest.mark.parametrize("enum", ["report_type", "report_status", "claim_status", "report_category", "status_actor"])
async def test_invalid_enum_labels_fail(db, enum):
    with pytest.raises(asyncpg.InvalidTextRepresentationError):
        await db.fetchval(f"SELECT 'invented-value'::{enum}")
