from uuid import uuid4

import asyncpg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from app.config import Settings
from app.db.generated.health import health_probe
from app.db.pool import lifespan
from app.errors import (
    DomainError, database_error, domain_error, error_response,
    http_error, unexpected_error, validation_error,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="FoundIt", lifespan=lifespan)
    app.state.settings = settings if settings is not None else Settings()
    for exception, handler in [
        (DomainError, domain_error), (RequestValidationError, validation_error),
        (HTTPException, http_error), (Exception, unexpected_error),
        (asyncpg.IntegrityConstraintViolationError, database_error),
    ]:
        app.add_exception_handler(exception, handler)

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.get("/health", tags=["Operations"])
    async def health(request: Request):
        try:
            async with request.app.state.pool.acquire(timeout=2) as conn:
                if await health_probe(conn) != 1:
                    raise RuntimeError("Unexpected health probe result")
        except (OSError, asyncpg.PostgresError, TimeoutError):
            return error_response(request, "database_unavailable", "Database unavailable", 503)
        return {"status": "ok"}

    return app
