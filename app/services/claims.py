from app.db.generated import claims, history
from app.db.generated.enums import ClaimStatus, ReportStatus, ReportType, StatusActor
from app.errors import DomainError
from app.security import issue_token


async def submit_claim(pool, report_id, values):
    raw, digest = issue_token()
    async with pool.acquire(timeout=2) as conn, conn.transaction():
        # SHARE permits other submissions but excludes report-closing writers.
        # Hold it through commit; future decisions lock report before claim.
        report = await claims.lock_report_for_claim(conn, id_=report_id)
        if report is None:
            raise DomainError("not_found", "Report not found", 404)
        if report.type != ReportType.FOUND or report.status != ReportStatus.OPEN:
            raise DomainError("claim_not_allowed", "Claims require an open found report", 409)
        claim_id = await claims.insert_claim(
            conn, report_id=report_id, **values, tracking_token_hash=memoryview(digest),
        )
        if claim_id is None:
            raise RuntimeError("Claim insert returned no id")
        event = await history.insert_claim_history(
            conn, claim_id=claim_id, from_status=None, to_status=ClaimStatus.PENDING,
            actor=StatusActor.OWNER, note=None,
        )
        if event is None:
            raise RuntimeError("Claim history insert returned no row")
    return {"id": claim_id, "tracking_token": raw}
