from pathlib import Path
from typing import Self

from pydantic import Field, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FOUNDIT_", env_file=".env", extra="ignore")

    database_url: PostgresDsn
    admin_key: SecretStr = Field(min_length=32)
    pool_size: int = Field(default=10, ge=1, le=50)
    default_page_size: int = Field(default=20, ge=1, le=100)
    max_page_size: int = Field(default=100, ge=1, le=200)
    match_window_days: int = Field(default=30, ge=1, le=365)
    upload_dir: Path = Path("uploads")
    max_photo_bytes: int = Field(default=5 * 1024 * 1024, ge=1, le=20 * 1024 * 1024)
    cors_origins: list[str] = Field(default_factory=list)

    @field_validator("database_url")
    @classmethod
    def native_postgres_scheme(cls, value: PostgresDsn) -> PostgresDsn:
        if value.scheme not in {"postgres", "postgresql"}:
            raise ValueError("Use a postgres:// or postgresql:// database URL")
        return value

    @model_validator(mode="after")
    def page_limits(self) -> Self:
        if self.default_page_size > self.max_page_size:
            raise ValueError("Default page size must not exceed the maximum")
        return self
