"""Direct SQL is intentional: constraint tests bypass application services."""
from hashlib import sha256
from uuid import uuid4


async def insert_report(db, **changes):
    values = dict(type="found", category="phone", title="Black phone",
                  description="Black phone with a distinctive case", location_text="Central station",
                  contact_name=None, contact_email=None, contact_phone=None,
                  tracking_token_hash=sha256(uuid4().bytes).digest(), photo_path=None)
    assert changes.keys() <= values.keys()
    values.update(changes)
    return await db.fetchrow("""
        INSERT INTO reports (type, category, title, description, location_text,
          contact_name, contact_email, contact_phone, tracking_token_hash, photo_path, event_date)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,CURRENT_DATE) RETURNING *
    """, *values.values())


async def insert_claim(db, report_id, **changes):
    values = dict(report_type="found", claimant_name="Claimant", claimant_contact="owner@example.com",
                  evidence="The case has my initials on its inside", tracking_token_hash=sha256(uuid4().bytes).digest())
    assert changes.keys() <= values.keys()
    values.update(changes)
    return await db.fetchrow("""
        INSERT INTO claims (report_id, report_type, claimant_name, claimant_contact, evidence, tracking_token_hash)
        VALUES ($1,$2,$3,$4,$5,$6) RETURNING *
    """, report_id, *values.values())
