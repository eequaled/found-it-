from scripts.migrations import check_migrations


async def test_migrations_up_down_up():
    await check_migrations()
