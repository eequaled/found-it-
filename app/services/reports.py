import asyncio
import logging

from app.db.generated import history, reports, search
from app.db.generated.enums import ReportStatus, StatusActor
from app.errors import DomainError
from app.security import issue_token, token_matches


async def create_report(pool, values: dict, *, photo_path=None, store=None):
    commit_started = False
    try:
        raw, digest = issue_token()
        async with pool.acquire(timeout=2) as conn, conn.transaction():
            report = await reports.insert_report(
                conn, **values, tracking_token_hash=memoryview(digest), photo_path=photo_path,
            )
            if report is None:
                raise RuntimeError("Report insert returned no row")
            event = await history.insert_report_history(
                conn, report_id=report.id_, from_status=None,
                to_status=ReportStatus.PENDING_REVIEW, actor=StatusActor.OWNER, note=None,
            )
            if event is None:
                raise RuntimeError("History insert returned no row")
            # Failure during COMMIT/release is ambiguous: retain the file for
            # offline reconciliation, rather than delete a committed reference.
            commit_started = True
    except BaseException:
        if store is not None and photo_path is not None and not commit_started:
            await asyncio.to_thread(store.delete, photo_path)
        raise
    return {"id": report.id_, "tracking_token": raw}


_pending_creations = set()
_creation_slots = asyncio.Semaphore(4)


def _finished(task):
    _pending_creations.discard(task)
    if not task.cancelled():
        error = task.exception()
        if error is not None and not isinstance(error, DomainError):
            logging.getLogger(__name__).error("Photo creation failed", exc_info=(type(error), error, error.__traceback__))


async def create_photo_report(pool, values, store, data):
    # No waiting queue of detached, multi-megabyte creation tasks.
    if _creation_slots.locked():
        raise DomainError("photo_busy", "Photo processing is busy; retry later", 503)
    await _creation_slots.acquire()

    async def work():
        try:
            saved = await asyncio.to_thread(store.save, data)
            return await create_report(pool, values, photo_path=saved.key, store=store)
        finally:
            _creation_slots.release()

    # A cancelled await must not abandon a writing thread or interrupt COMMIT.
    # Disconnected requests may still commit, just as with lost token delivery.
    task = asyncio.create_task(work())
    _pending_creations.add(task)
    task.add_done_callback(_finished)
    return await asyncio.shield(task)


async def get_public_photo(pool, report_id, store):
    async with pool.acquire(timeout=2) as conn:
        key = await reports.get_public_photo(conn, id_=report_id)
    if key is None:
        raise DomainError("not_found", "Photo not found", 404)
    return await asyncio.to_thread(store.load, key)


async def search_public(pool, values, page_size):
    filters = dict(values)
    page = filters.pop("page")
    filters.pop("page_size")
    location = filters.pop("location")
    # SQL wildcards are literal user characters, not an extra query language.
    pattern = None if location is None else "%" + location.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    async with pool.acquire(timeout=2) as conn:
        rows = await search.search_public_reports(
            conn, **filters, location_pattern=pattern,
            page_size=page_size, page_offset=(page - 1) * page_size,
        )
    return {"items": [row for row in rows if row.id_ is not None],
            "total": rows[0].total, "page": page, "page_size": page_size}


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
