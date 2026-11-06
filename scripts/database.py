"""Disposable databases owned by this test run, never the supplied database."""
import os
from contextlib import asynccontextmanager
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import asyncpg


@asynccontextmanager
async def temporary_database(base_url: str):
    name = "foundit_test_" + uuid4().hex
    parts = urlsplit(base_url)
    url = urlunsplit(parts._replace(path="/" + name))
    admin = await asyncpg.connect(base_url, timeout=5, command_timeout=10)
    created = False
    try:
        # Identifier is generated here, never taken from user input.
        await admin.execute(f'CREATE DATABASE "{name}"')
        created = True
        yield url
    finally:
        try:
            if created:
                await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        finally:
            await admin.close(timeout=5)


def test_database_url():
    return os.environ["TEST_DATABASE_URL"]
