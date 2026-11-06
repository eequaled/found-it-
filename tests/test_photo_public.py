from uuid import uuid4

import pytest

from tests.report_helpers import report_payload
from tests.test_photo_api import submit


async def test_photo_is_private_until_open_and_hidden_by_every_nonpublic_status(api, db, settings):
    body = (await submit(api)).json()
    row = await db.fetchrow("SELECT * FROM reports WHERE id=$1::text::uuid", body["id"])
    key = row["photo_path"]
    url = f"/reports/{body['id']}/photo"
    for status in ("pending_review", "open", "resolved", "removed", "rejected"):
        await db.execute("UPDATE reports SET status=$1 WHERE id=$2", status, row["id"])
        photo = await api.get(url)
        assert photo.headers["cache-control"] == "no-store"
        if status == "open":
            assert photo.status_code == 200 and photo.headers["content-type"] == "image/png"
            assert photo.headers["x-content-type-options"] == "nosniff"
            assert photo.content == (settings.upload_dir / key).read_bytes()
            public = (await api.get(f"/reports/{body['id']}")).json()
            assert "photo_path" not in public and "tracking_token" not in public
        else:
            assert photo.status_code == 404 and key not in photo.text
    (settings.upload_dir / key).unlink()
    await db.execute("UPDATE reports SET status='open' WHERE id=$1", row["id"])
    assert (await api.get(url)).status_code == 404
    assert (await api.get(f"/reports/{uuid4()}/photo")).status_code == 404


async def test_photo_openapi_describes_binary_images_not_json(api):
    operation = (await api.get("/openapi.json")).json()["paths"]["/reports/{report_id}/photo"]["get"]
    assert set(operation["responses"]["200"]["content"]) == {"image/jpeg", "image/png", "image/webp"}


async def test_open_report_without_photo_returns_404(api, db):
    response = await api.post("/reports", json=report_payload())
    await db.execute("UPDATE reports SET status='open'")
    assert (await api.get(f"/reports/{response.json()['id']}/photo")).status_code == 404


@pytest.mark.parametrize("kind,mime", [("JPEG", "image/jpeg"), ("WEBP", "image/webp")])
async def test_public_photo_uses_detected_mime_for_each_allowed_format(api, db, kind, mime):
    from tests.test_photo_storage import picture

    response = await submit(api, picture(kind))
    assert response.status_code == 201
    await db.execute("UPDATE reports SET status='open'")
    photo = await api.get(f"/reports/{response.json()['id']}/photo")
    assert photo.status_code == 200 and photo.headers["content-type"] == mime
