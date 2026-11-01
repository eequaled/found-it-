from uuid import UUID

import asyncpg
import httpx
import pytest
from pydantic import BaseModel

from app.main import create_app


@pytest.fixture
def app(settings, pool):
    value = create_app(settings)
    value.state.pool = pool
    return value


@pytest.fixture
async def client(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as session:
        yield session


async def test_health_and_server_generated_request_id(client):
    response = await client.get("/health", headers={"X-Request-ID": "untrusted-input"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert UUID(response.headers["X-Request-ID"]).version == 4
    assert (await client.get("/health")).headers["X-Request-ID"] != response.headers["X-Request-ID"]


@pytest.mark.parametrize("failure", [OSError, TimeoutError, asyncpg.PostgresError])
async def test_health_database_unavailable(client, pool, failure):
    pool.acquire.return_value.__aenter__.return_value.fetchrow.side_effect = failure("private DSN")
    response = await client.get("/health")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert "private DSN" not in response.text


async def test_missing_route_method_and_docs(client):
    assert (await client.get("/missing")).json()["error"]["code"] == "not_found"
    response = await client.post("/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
    assert "GET" in response.headers["allow"]
    assert (await client.get("/docs")).status_code == 200


async def test_registered_validation_and_unexpected_error_handlers(app, client, caplog):
    class Payload(BaseModel):
        count: int

    @app.post("/validation")
    async def validate(body: Payload):
        return body

    @app.get("/unexpected")
    async def fail():
        raise RuntimeError("SELECT private_column")

    response = await client.post("/validation", json={"count": "private-contact-value"})
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body.count"
    assert "private-contact-value" not in response.text
    response = await client.get("/unexpected?token=secret-query-value")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "SELECT" not in response.text
    assert response.headers["X-Request-ID"] in caplog.text
    assert "secret-query-value" not in caplog.text
