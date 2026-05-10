import os
from collections.abc import AsyncIterator

import pytest_asyncio
from app.db.models import Base
from app.db.session import create_engine, create_session_factory
from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://linkdooni:linkdooni@localhost:5432/linkdooni_test"
)


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    database_url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    engine = create_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    async with session_factory() as db_session:
        yield db_session
        await db_session.rollback()
    await engine.dispose()
