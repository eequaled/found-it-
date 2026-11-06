"""Bound report bodies before multipart parsing; share JSON/form validation."""
import asyncio

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from python_multipart.exceptions import MultipartParseError
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.api.schemas import ReportCreate
from app.errors import DomainError, error_response
from app.storage import read_upload


class ReportBodyLimit:
    def __init__(self, app, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"].rstrip("/") != "/reports":
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.limit:
                response = error_response(Request(scope), "request_too_large", "Report request is too large", 413)
                return await response(scope, receive, send)
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        sent = False

        async def replay():
            nonlocal sent
            if sent:
                return await receive()
            sent = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)


def validate(values):
    try:
        return ReportCreate.model_validate(values)
    except ValidationError as exc:
        raise RequestValidationError([
            {**error, "loc": ("body", *error["loc"])} for error in exc.errors()
        ]) from None


async def parse_report(request: Request):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type == "application/json":
        try:
            values = await request.json()
        except ValueError:
            raise RequestValidationError([{"loc": ("body",), "type": "json_invalid", "msg": "Invalid JSON"}]) from None
        return validate(values).model_dump(), None
    if content_type != "multipart/form-data":
        raise DomainError("unsupported_media_type", "Use application/json or multipart/form-data", 415)
    parser = MultiPartParser(request.headers, request.stream(), max_files=1, max_fields=10, max_part_size=16384)
    try:
        form = await parser.parse()
        if len(form.multi_items()) != len(form):
            raise DomainError("validation_error", "Duplicate form fields are not allowed", 422)
        photo = form.get("photo")
        if photo is not None and not isinstance(photo, UploadFile):
            raise DomainError("invalid_photo", "Photo must be an uploaded file", 422)
        values = validate({key: value for key, value in form.items() if key != "photo"})
        data = await read_upload(photo, request.app.state.settings.max_photo_bytes) if photo else None
        return values.model_dump(), data
    except (MultiPartException, MultipartParseError):
        raise DomainError("validation_error", "Invalid multipart report", 422) from None
    finally:
        # Starlette only closes these itself for MultiPartException, not low-level
        # parse errors/cancellation. Keep this private-API dependency tested.
        for file in parser._files_to_close_on_error:
            await asyncio.to_thread(file.close)


def creation_body_schema():
    schema = ReportCreate.model_json_schema()
    definitions = schema.pop("$defs", {})
    for field in schema["properties"].values():
        if "$ref" in field:
            field.update(definitions[field.pop("$ref").rsplit("/", 1)[-1]])
    form_schema = {**schema, "properties": {**schema["properties"], "photo": {"type": "string", "format": "binary"}}}
    return {"requestBody": {"required": True, "content": {
        "application/json": {"schema": schema}, "multipart/form-data": {"schema": form_schema},
    }}}
