import asyncio
from uuid import UUID

import asyncpg

from app.db.generated import claims, history
from tests.test_claim_submission import submit
from tests.test_search import candidate


async def test_submission_holds_share_lock_through_initial_history_and_commit(api, db, database_url, monkeypatch):
    report, reached, release = await candidate(db), asyncio.Event(), asyncio.Event()
    original = history.insert_claim_history

    async def paused(conn, **kwargs):
        reached.set()
        await asyncio.wait_for(release.wait(), 5)
        return await original(conn, **kwargs)

    monkeypatch.setattr(history, "insert_claim_history", paused)
    observer = await asyncpg.connect(database_url)
    submission = asyncio.create_task(submit(api, report))
    writer = None
    try:
        await asyncio.wait_for(reached.wait(), 3)
        writer = asyncio.create_task(db.fetchrow("SELECT id FROM reports WHERE id=$1 FOR UPDATE", UUID(report)))
        async with asyncio.timeout(3):
            while not await observer.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_locks WHERE pid=$1 AND NOT granted)", db.get_server_pid(),
            ):
                await asyncio.sleep(0.01)
        release.set()
        assert (await asyncio.wait_for(submission, 5)).status_code == 201
        await asyncio.wait_for(writer, 5)
        assert await db.fetchval("SELECT count(*) FROM claims") == 1
        assert await db.fetchval("SELECT count(*) FROM claim_status_history") == 1
    finally:
        release.set()
        for task in (submission, writer):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(*(task for task in (submission, writer) if task is not None), return_exceptions=True)
        await observer.close()


async def test_submission_waits_for_closing_writer_then_rechecks_state(api, db, monkeypatch):
    report, attempted, pids = await candidate(db), asyncio.Event(), []
    original = claims.lock_report_for_claim

    async def observed(conn, **kwargs):
        pids.append(conn.get_server_pid())
        attempted.set()
        return await original(conn, **kwargs)

    monkeypatch.setattr(claims, "lock_report_for_claim", observed)
    tx = db.transaction()
    await tx.start()
    await db.fetchrow("SELECT id FROM reports WHERE id=$1 FOR UPDATE", UUID(report))
    task = asyncio.create_task(submit(api, report))
    try:
        await asyncio.wait_for(attempted.wait(), 3)
        # Prove it is actually waiting in PostgreSQL, not just scheduled later.
        async with asyncio.timeout(3):
            while not await db.fetchval("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE pid=$1 AND NOT granted)", pids[0]):
                await asyncio.sleep(0.01)
        await db.execute("UPDATE reports SET status='resolved' WHERE id=$1", UUID(report))
        await tx.commit()
        response = await asyncio.wait_for(task, 5)
        assert response.status_code == 409
        assert await db.fetchval("SELECT count(*) FROM claims") == 0
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if db.is_in_transaction():
            await tx.rollback()
