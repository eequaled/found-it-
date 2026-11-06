import pytest
from pydantic import ValidationError

from app.config import Settings


def test_environment_settings_and_redacted_key(monkeypatch):
    monkeypatch.setenv("FOUNDIT_DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("FOUNDIT_ADMIN_KEY", "secret-admin-key-" * 3)
    monkeypatch.setenv("FOUNDIT_POOL_SIZE", "4")
    value = Settings(_env_file=None)
    assert value.pool_size == 4
    assert value.admin_key.get_secret_value() == "secret-admin-key-" * 3
    assert "secret-admin-key-" not in repr(value)


@pytest.mark.parametrize("override", [
    {"database_url": "postgresql+asyncpg://u:p@localhost/db"},
    {"admin_key": "short"}, {"pool_size": 0}, {"max_photo_bytes": 0},
    {"default_page_size": 50, "max_page_size": 10},
])
def test_invalid_settings_fail_before_startup(override):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{
            "database_url": "postgresql://user:pass@localhost/db",
            "admin_key": "a" * 32, **override,
        })
