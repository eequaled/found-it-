from uuid import UUID

from fastapi import APIRouter, Header, Request, Response

from app.api.report_input import creation_body_schema, parse_report
from app.api.schemas import PublicReport, ReportCreated, ReportMatches, ReportOwnerStatus
from app.services import matching, reports

router = APIRouter(prefix="/reports")


@router.post("", response_model=ReportCreated, status_code=201, tags=["Public reports"], openapi_extra=creation_body_schema())
async def create_report(request: Request):
    values, photo = await parse_report(request)
    if photo is not None:
        return await reports.create_photo_report(request.app.state.pool, values, request.app.state.photos, photo)
    return await reports.create_report(request.app.state.pool, values)


@router.get("/{report_id}/photo", tags=["Public reports"], response_class=Response, responses={
    200: {"content": {mime: {"schema": {"type": "string", "format": "binary"}}
                      for mime in ("image/jpeg", "image/png", "image/webp")}},
})
async def get_photo(report_id: UUID, request: Request):
    content, media_type = await reports.get_public_photo(request.app.state.pool, report_id, request.app.state.photos)
    return Response(content, media_type=media_type, headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.get("/{report_id}/matches", response_model=ReportMatches, tags=["Public reports"])
async def get_matches(report_id: UUID, request: Request):
    return await matching.find_matches(
        request.app.state.pool, report_id, request.app.state.settings.match_window_days,
    )


@router.get("/{report_id}", response_model=PublicReport, tags=["Public reports"])
async def get_report(report_id: UUID, request: Request):
    row = await reports.get_public_report(request.app.state.pool, report_id)
    return PublicReport.model_validate(row)


@router.get("/{report_id}/status", response_model=ReportOwnerStatus, tags=["Owner tracking"])
async def get_status(report_id: UUID, request: Request, token: str | None = Header(default=None, alias="X-Tracking-Token")):
    return await reports.get_owner_status(request.app.state.pool, report_id, token)
