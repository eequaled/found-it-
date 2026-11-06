from fastapi import APIRouter, Request

from app.api.schemas import ReportCreate, ReportCreated
from app.services import reports

router = APIRouter(prefix="/reports")


@router.post("", response_model=ReportCreated, status_code=201, tags=["Public reports"])
async def create_report(payload: ReportCreate, request: Request):
    return await reports.create_report(request.app.state.pool, payload.model_dump())
