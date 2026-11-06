from uuid import UUID

from fastapi import APIRouter, Header, Request

from app.api.schemas import PublicReport, ReportCreate, ReportCreated, ReportOwnerStatus
from app.services import reports

router = APIRouter(prefix="/reports")


@router.post("", response_model=ReportCreated, status_code=201, tags=["Public reports"])
async def create_report(payload: ReportCreate, request: Request):
    return await reports.create_report(request.app.state.pool, payload.model_dump())


@router.get("/{report_id}", response_model=PublicReport, tags=["Public reports"])
async def get_report(report_id: UUID, request: Request):
    row = await reports.get_public_report(request.app.state.pool, report_id)
    return PublicReport.model_validate(row)


@router.get("/{report_id}/status", response_model=ReportOwnerStatus, tags=["Owner tracking"])
async def get_status(report_id: UUID, request: Request, token: str | None = Header(default=None, alias="X-Tracking-Token")):
    return await reports.get_owner_status(request.app.state.pool, report_id, token)
