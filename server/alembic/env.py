"""Alembic environment. Run by infra/deploy.sh only, never on app startup (invariant 10)."""

import asyncio
import os

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://", 1)


def _run(conn) -> None:
    context.configure(connection=conn, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


async def _online() -> None:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        await conn.run_sync(_run)
    await engine.dispose()


asyncio.run(_online())
