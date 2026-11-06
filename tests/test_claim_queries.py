from uuid import UUID, uuid4

from app.db.generated import claims
from app.db.generated.enums import ReportStatus, ReportType
from app.security import issue_token
from tests.test_search import candidate


async def test_claim_query_decode_and_scalar_insert_id(db):
    report_id = UUID(await candidate(db))
    assert await claims.lock_report_for_claim(db, id_=uuid4()) is None
    _, digest = issue_token()
    async with db.transaction():
        report = await claims.lock_report_for_claim(db, id_=report_id)
        assert report.type == ReportType.FOUND and report.status == ReportStatus.OPEN
        claim_id = await claims.insert_claim(
            db, report_id=report_id, claimant_name="Owner", claimant_contact="owner@example.com",
            evidence="Private identifying evidence", tracking_token_hash=memoryview(digest),
        )
        assert isinstance(claim_id, UUID)
    assert await db.fetchval("SELECT status FROM claims WHERE id=$1", claim_id) == "pending"
