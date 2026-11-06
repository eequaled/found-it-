from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.services import claims


class ClaimCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    claimant_name: str = Field(min_length=1, max_length=100)
    claimant_contact: str = Field(min_length=3, max_length=254)
    evidence: str = Field(min_length=10, max_length=5000)


class ClaimCreated(BaseModel):
    id: UUID
    tracking_token: str


router = APIRouter()


@router.post("/reports/{report_id}/claims", response_model=ClaimCreated, status_code=201, tags=["Public claims"])
async def submit_claim(report_id: UUID, payload: ClaimCreate, request: Request):
    return await claims.submit_claim(request.app.state.pool, report_id, payload.model_dump())
