from collections.abc import AsyncIterator

import pytest_asyncio
from app.db.session import create_engine, create_session_factory, init_db
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncIterator[AsyncSession]:  # type: ignore[no-untyped-def]
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(database_url)
    await init_db(engine)
    session_factory = create_session_factory(engine)
    async with session_factory() as db_session:
        yield db_session
        await db_session.rollback()
    await engine.dispose()
