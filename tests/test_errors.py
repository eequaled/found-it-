import json

import asyncpg
import pytest
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.requests import Request

from app.errors import (
    DomainError, database_error, domain_error, http_error,
    unexpected_error, validation_error,
)


@pytest.fixture
def request_context():
    request = Request({"type": "http", "method": "GET", "path": "/failure",
                       "headers": [], "query_string": b"token=secret-query-value"})
    request.state.request_id = "server-generated-id"
    return request


@pytest.mark.parametrize("handler,failure,status,code", [
    (domain_error, DomainError("not_found", "Missing resource", 404), 404, "not_found"),
    (domain_error, DomainError("invalid_transition", "Invalid state"), 409, "invalid_transition"),
    (http_error, HTTPException(401, "Admin key required", headers={"WWW-Authenticate": "AdminKey"}),
     401, "unauthorized"),
    (database_error, asyncpg.UniqueViolationError("private SQL"), 409, "conflict"),
    (database_error, asyncpg.ForeignKeyViolationError("private SQL"), 422, "invalid_input"),
    (database_error, asyncpg.CheckViolationError("private SQL"), 422, "invalid_input"),
    (database_error, asyncpg.NotNullViolationError("private SQL"), 422, "invalid_input"),
])
async def test_error_mapping(request_context, handler, failure, status, code):
    response = await handler(request_context, failure)
    assert response.status_code == status
    assert json.loads(response.body)["error"]["code"] == code
    assert b"private SQL" not in response.body
    assert response.headers["X-Request-ID"] == "server-generated-id"
    if status == 401:
        assert response.headers["WWW-Authenticate"] == "AdminKey"


async def test_validation_does_not_echo_sensitive_input(request_context):
    response = await validation_error(request_context, RequestValidationError([
        {"loc": ("body", "count"), "msg": "Invalid integer", "type": "int_parsing",
         "input": "private-contact-value", "ctx": {"secret": "private-context"}},
    ]))
    assert response.status_code == 422
    assert json.loads(response.body)["error"]["details"][0]["field"] == "body.count"
    assert b"private-" not in response.body


async def test_unexpected_error_logs_context_not_query(request_context, caplog):
    response = await unexpected_error(request_context, RuntimeError("SELECT private_column"))
    assert response.status_code == 500
    assert json.loads(response.body)["error"]["code"] == "internal_error"
    assert b"SELECT" not in response.body
    assert "method=GET path=/failure request_id=server-generated-id" in caplog.text
    assert "secret-query-value" not in caplog.text
