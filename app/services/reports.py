from app.db.generated import history, reports
from app.db.generated.enums import ReportStatus, StatusActor
from app.errors import DomainError
from app.security import issue_token, token_matches


async def create_report(pool, values: dict):
    raw, digest = issue_token()
    async with pool.acquire(timeout=2) as conn, conn.transaction():
        report = await reports.insert_report(
            conn, **values, tracking_token_hash=memoryview(digest), photo_path=None,
        )
        if report is None:
            raise RuntimeError("Report insert returned no row")
        event = await history.insert_report_history(
            conn, report_id=report.id_, from_status=None,
            to_status=ReportStatus.PENDING_REVIEW, actor=StatusActor.OWNER, note=None,
        )
        if event is None:
            raise RuntimeError("History insert returned no row")
    # Never return a token for an uncommitted report.
    return {"id": report.id_, "tracking_token": raw}


async def get_public_report(pool, report_id):
    async with pool.acquire(timeout=2) as conn:
        report = await reports.get_public_report(conn, id_=report_id)
    if report is None:
        raise DomainError("not_found", "Report not found", 404)
    return report


async def get_owner_status(pool, report_id, token: str | None):
    async with pool.acquire(timeout=2) as conn, conn.transaction(isolation="repeatable_read", readonly=True):
        report = await reports.get_report_owner_access(conn, id_=report_id)
        if report is None or not token_matches(token, report.tracking_token_hash):
            raise DomainError("not_found", "Report not found", 404)
        events = await history.get_report_history(conn, report_id=report_id)
    return {"id": report.id_, "status": report.status, "history": events}
