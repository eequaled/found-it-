import httpx
import pytest

from app.db.generated.enums import ReportStatus as R
from app.main import create_app
from app.services.transitions import require_valid_report_transition


@pytest.mark.parametrize("current,target,status,code", [
    (R.RESOLVED, R.OPEN, 409, "invalid_transition"),
    (R.OPEN, R.REMOVED, 422, "invalid_note"),
])
async def test_guard_errors_use_existing_http_envelope(settings, current, target, status, code):
    app = create_app(settings)

    # Test-only transport harness, not a production mutation endpoint.
    @app.post("/_test/transition")
    async def transition():
        require_valid_report_transition(current, target)
        return {}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/_test/transition")
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]
