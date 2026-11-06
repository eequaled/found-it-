import asyncio
import io
import threading
from unittest.mock import AsyncMock

import asyncpg
import pytest
from PIL import Image

from app.api.schemas import ReportCreate
from app.services import reports
from app.storage import PhotoStore
from tests.report_helpers import report_payload


def image():
    output = io.BytesIO()
    Image.new("RGB", (3, 2), "red").save(output, "PNG")
    return output.getvalue()


async def submit(api, data=None, **fields):
    return await api.post("/reports", data=report_payload(**fields),
                          files={"photo": ("../../private.svg", image() if data is None else data, "text/html")})


async def test_create_photo_stores_only_opaque_key_and_commits_initial_history(api, db, settings):
    response = await submit(api)
    assert response.status_code == 201 and set(response.json()) == {"id", "tracking_token"}
    row = await db.fetchrow("SELECT * FROM reports WHERE id=$1::text::uuid", response.json()["id"])
    key = row["photo_path"]
    assert "/" not in key and key.endswith(".png")
    assert (settings.upload_dir / key).exists() and row["status"] == "pending_review"
    assert await db.fetchval("SELECT count(*) FROM report_status_history") == 1


@pytest.mark.parametrize("data", [b"not an image", b"", b"x" * (5 * 1024 * 1024 + 1)], ids=["invalid", "empty", "too_large"])
async def test_bad_photo_never_creates_report_or_file(api, db, settings, data):
    response = await submit(api, data)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_photo"
    assert await db.fetchval("SELECT count(*) FROM reports") == 0
    assert not settings.upload_dir.exists()


async def test_invalid_form_fields_and_duplicate_fields_write_nothing(api, db, settings):
    response = await submit(api, title=" ", contact_email="private-invalid")
    assert response.status_code == 422 and "private-invalid" not in response.text
    assert {item["field"] for item in response.json()["error"]["details"]} == {"body.title", "body.contact_email"}
    response = await api.post("/reports", data={**report_payload(), "title": ["First phone", "Second phone"]},
                              files={"photo": ("x.png", image())})
    assert response.status_code == 422
    assert await db.fetchval("SELECT count(*) FROM reports") == 0
    assert not settings.upload_dir.exists()


async def test_multipart_without_photo_stays_supported(api, db):
    response = await api.post("/reports", files={key: (None, value) for key, value in report_payload().items()})
    assert response.status_code == 201
    assert await db.fetchval("SELECT photo_path FROM reports") is None


@pytest.mark.parametrize("target", ["reports.insert_report", "history.insert_report_history"])
async def test_known_rollback_deletes_photo_and_all_database_rows(api, db, settings, monkeypatch, target):
    monkeypatch.setattr("app.services.reports." + target, AsyncMock(side_effect=RuntimeError("forced failure")))
    response = await submit(api)
    assert response.status_code == 500 and "tracking_token" not in response.text
    assert list(settings.upload_dir.iterdir()) == []
    assert await db.fetchval("SELECT count(*) FROM reports") == 0
    assert await db.fetchval("SELECT count(*) FROM report_status_history") == 0


async def test_lost_commit_ack_keeps_photo_referenced_by_committed_row(api, db, settings, monkeypatch):
    original = asyncpg.Connection.transaction

    class LostAck:
        def __init__(self, tx):
            self.tx = tx

        async def __aenter__(self):
            return await self.tx.__aenter__()

        async def __aexit__(self, *args):
            result = await self.tx.__aexit__(*args)
            if args[0] is None:
                raise ConnectionError("lost commit acknowledgement")
            return result

    monkeypatch.setattr(asyncpg.Connection, "transaction", lambda conn, *args, **kw: LostAck(original(conn, *args, **kw)))
    response = await submit(api)
    assert response.status_code == 500
    key = await db.fetchval("SELECT photo_path FROM reports")
    assert (settings.upload_dir / key).exists()
    assert await db.fetchval("SELECT count(*) FROM report_status_history") == 1


async def test_request_cancellation_does_not_abandon_writing_worker(database_url, db, settings, monkeypatch):
    store = PhotoStore(settings.upload_dir, settings.max_photo_bytes)
    started, release = threading.Event(), threading.Event()
    original = store.save

    def delayed(data):
        started.set()
        assert release.wait(5)
        return original(data)

    monkeypatch.setattr(store, "save", delayed)
    async with asyncpg.create_pool(database_url) as pool:
        task = asyncio.create_task(reports.create_photo_report(
            pool, ReportCreate(**report_payload()).model_dump(), store, image(),
        ))
        try:
            assert await asyncio.to_thread(started.wait, 3)
            pending = list(reports._pending_creations)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()
        await asyncio.gather(*pending)
    key = await db.fetchval("SELECT photo_path FROM reports")
    assert store.load(key)[0] and len(list(settings.upload_dir.iterdir())) == 1


async def test_oversized_chunked_request_stops_before_multipart_parser(api, db, monkeypatch):
    async def chunks():
        for _ in range(6):
            yield b"x" * (1024 * 1024)

    monkeypatch.setattr("app.api.report_input.MultiPartParser", lambda *args, **kw: pytest.fail("parser ran"))
    response = await api.post("/reports", content=chunks(), headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert response.status_code == 413 and response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]
    assert await db.fetchval("SELECT count(*) FROM reports") == 0


@pytest.mark.parametrize("content,content_type,status", [(b"{", "application/json", 422), (b"x", "text/plain", 415),
                                                        (b"x", "multipart/form-data", 422), (b"broken", "multipart/form-data; boundary=x", 422)])
async def test_malformed_or_unsupported_body_uses_safe_error_envelope(api, content, content_type, status):
    response = await api.post("/reports", content=content, headers={"Content-Type": content_type})
    assert response.status_code == status and "error" in response.json()


async def test_photo_capacity_rejects_without_starting_more_detached_work(api, db, settings, monkeypatch):
    monkeypatch.setattr(reports, "_creation_slots", asyncio.Semaphore(0))
    response = await submit(api)
    assert response.status_code == 503 and response.json()["error"]["code"] == "photo_busy"
    assert not settings.upload_dir.exists()
    assert await db.fetchval("SELECT count(*) FROM reports") == 0


async def test_malformed_multipart_closes_already_created_spool_files(api, monkeypatch):
    from starlette import formparsers

    original, files = formparsers.SpooledTemporaryFile, []

    def track(*args, **kwargs):
        file = original(*args, **kwargs)
        files.append(file)
        return file

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", track)
    body = (b'--x\r\nContent-Disposition: form-data; name="photo"; filename="a.png"\r\n\r\npixels\r\n'
            b'--x\r\nbad header\r\n\r\nbroken\r\n--x--\r\n')
    response = await api.post("/reports", content=body, headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert response.status_code == 422 and files and all(file.closed for file in files)


async def test_openapi_documents_both_creation_formats(api):
    body = (await api.get("/openapi.json")).json()["paths"]["/reports"]["post"]["requestBody"]["content"]
    assert body["application/json"]["schema"]["properties"]["type"]["enum"] == ["lost", "found"]
    assert body["multipart/form-data"]["schema"]["properties"]["photo"]["format"] == "binary"
