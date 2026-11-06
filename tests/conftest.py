import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings


@pytest.fixture
def settings():
    return Settings(
        _env_file=None, database_url=os.environ.get(
            "TEST_DATABASE_URL", "postgresql://foundit:foundit@localhost:5432/foundit_test"
        ), admin_key="a" * 32, cors_origins=["https://staff.example"],
    )


@pytest.fixture
def pool():
    value = MagicMock()
    value.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(return_value=(1,))
    value.close = AsyncMock()
    return value
