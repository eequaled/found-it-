from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import Field, field_validator, model_validator

from app.api.pagination import Page, Pagination
from app.api.schemas import PublicReport, ReportCreate
from app.db.generated.enums import ReportCategory, ReportType
from app.services import reports


class ReportSearch(Pagination):
    q: str | None = Field(default=None, max_length=200)
    type: ReportType | None = None
    category: ReportCategory | None = None
    date_from: date | None = None
    date_to: date | None = None
    location: str | None = Field(default=None, max_length=200)

    @field_validator("q", "location")
    @classmethod
    def blank_means_browse(cls, value):
        return value or None

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def calendar_dates(cls, value):
        return ReportCreate.calendar_date(value) if value is not None else None

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not exceed date_to")
        return self


router = APIRouter()


@router.get("/reports", response_model=Page[PublicReport], tags=["Public reports"])
async def search_reports(request: Request, filters: Annotated[ReportSearch, Query()]):
    settings = request.app.state.settings
    size = filters.page_size if filters.page_size is not None else settings.default_page_size
    if size > settings.max_page_size:
        raise RequestValidationError([{"loc": ("query", "page_size"), "type": "less_than_equal",
                                       "msg": f"Page size must not exceed {settings.max_page_size}"}])
    return await reports.search_public(request.app.state.pool, filters.model_dump(), size)
