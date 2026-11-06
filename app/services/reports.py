from app.db.generated import history, reports
from app.db.generated.enums import ReportStatus, StatusActor
from app.security import issue_token


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
