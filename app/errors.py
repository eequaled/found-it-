import logging

import asyncpg
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class DomainError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


def error_response(request: Request, code: str, message: str, status: int,
                   details=None, headers=None):
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(
        {"error": error}, status_code=status,
        headers={**(headers or {}), "X-Request-ID": request.state.request_id},
    )


async def domain_error(request: Request, exc: DomainError):
    return error_response(request, exc.code, exc.message, exc.status_code)


async def validation_error(request: Request, exc: RequestValidationError):
    # Omit rejected input and exception contexts, which can contain secrets.
    details = [{"field": ".".join(map(str, item["loc"])),
                "message": item["msg"], "type": item["type"]} for item in exc.errors()]
    return error_response(request, "validation_error", "Invalid request", 422, details)


async def http_error(request: Request, exc: HTTPException):
    codes = {401: "unauthorized", 404: "not_found", 405: "method_not_allowed"}
    return error_response(request, codes.get(exc.status_code, "http_error"),
                          str(exc.detail), exc.status_code, headers=exc.headers)


async def database_error(request: Request, exc: asyncpg.IntegrityConstraintViolationError):
    if isinstance(exc, asyncpg.UniqueViolationError):
        return error_response(request, "conflict", "A conflicting record already exists", 409)
    return error_response(request, "invalid_input", "Database constraint rejected the input", 422)


async def unexpected_error(request: Request, exc: Exception):
    logger.error("Unhandled request failure: method=%s path=%s request_id=%s",
                 request.method, request.url.path, request.state.request_id,
                 exc_info=(type(exc), exc, exc.__traceback__))
    return error_response(request, "internal_error", "An unexpected error occurred", 500)
