from datetime import UTC, date, datetime
import re
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.db.generated.enums import ReportCategory, ReportType


class ReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    type: ReportType
    category: ReportCategory
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=5000)
    event_date: date
    location_text: str = Field(min_length=2, max_length=200)
    contact_name: str | None = Field(default=None, min_length=1, max_length=100)
    contact_email: Annotated[EmailStr, Field(max_length=254)] | None = None
    contact_phone: str | None = Field(default=None, min_length=3, max_length=40, pattern=r"^\+?[0-9() .-]+$")

    @field_validator("event_date", mode="before")
    @classmethod
    def calendar_date(cls, value):
        if type(value) is date or (isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value)):
            return value
        raise ValueError("Use an ISO calendar date (YYYY-MM-DD)")

    @field_validator("event_date")
    @classmethod
    def not_in_future(cls, value: date) -> date:
        if value > datetime.now(UTC).date():
            raise ValueError("Event date must not be in the future (UTC)")
        return value

    @field_validator("contact_phone")
    @classmethod
    def phone_digits(cls, value: str | None) -> str | None:
        if value is not None and sum(char.isdigit() for char in value) < 3:
            raise ValueError("Phone must contain at least three digits")
        return value


class ReportCreated(BaseModel):
    id: UUID
    tracking_token: str
