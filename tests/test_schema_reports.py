import asyncpg
import pytest

from tests.schema_helpers import insert_report


async def test_report_defaults_and_generated_multilingual_search(db):
    row = await insert_report(db, title="هاتف téléphone phone")
    assert row["status"] == "pending_review"
    assert row["created_at"] == row["updated_at"]
    assert row["contact_email"] is None and row["contact_phone"] is None
    assert len(row["tracking_token_hash"]) == 32
    for keyword in ["هاتف", "téléphone", "phone"]:
        assert await db.fetchval(
            "SELECT search_vector @@ plainto_tsquery('simple', $2) FROM reports WHERE id=$1",
            row["id"], keyword,
        )
    await db.execute("UPDATE reports SET title='Distinctive replacement' WHERE id=$1", row["id"])
    assert await db.fetchval(
        "SELECT search_vector @@ plainto_tsquery('simple','replacement') FROM reports WHERE id=$1",
        row["id"],
    )


@pytest.mark.parametrize("changes", [
    {"title": "ab"}, {"title": "x" * 121}, {"title": "\t\n "},
    {"description": "short"}, {"description": "x" * 5001}, {"description": " " * 10},
    {"location_text": "x"}, {"location_text": "x" * 201},
    {"contact_name": ""}, {"contact_email": " " * 3}, {"contact_phone": "x" * 41},
    {"tracking_token_hash": b"short"}, {"photo_path": "../../private.jpg"},
])
async def test_report_checks_cannot_be_bypassed(db, changes):
    with pytest.raises(asyncpg.CheckViolationError):
        await insert_report(db, **changes)


async def test_report_boundaries_optional_contacts_and_photo(db):
    row = await insert_report(
        db, title="x" * 120, description="x" * 5000, location_text="x" * 200,
        contact_name="x" * 100, contact_email="x" * 254, contact_phone="x" * 40,
        photo_path="a" * 32 + ".webp",
    )
    assert row["photo_path"] == "a" * 32 + ".webp"
    with pytest.raises(asyncpg.UniqueViolationError):
        await insert_report(db, tracking_token_hash=row["tracking_token_hash"])
    with pytest.raises(asyncpg.NotNullViolationError):
        await insert_report(db, type=None)
    with pytest.raises(asyncpg.GeneratedAlwaysError):
        await db.execute("UPDATE reports SET search_vector=''::tsvector WHERE id=$1", row["id"])
