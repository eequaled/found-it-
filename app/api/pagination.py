from pydantic import BaseModel, ConfigDict, Field


class Pagination(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    page: int = Field(default=1, ge=1, le=1_000_000)
    page_size: int | None = Field(default=None, ge=1, le=200)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
