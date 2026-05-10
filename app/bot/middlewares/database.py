from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.types import User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.repositories.users import UserRepository
from app.utils.i18n import MessageCatalog


class DatabaseMiddleware(BaseMiddleware):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        catalog: MessageCatalog,
        *,
        default_language: str,
    ) -> None:
        self.session_factory = session_factory
        self.catalog = catalog
        self.default_language = default_language

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            data["messages"] = self.catalog
            telegram_user = data.get("event_from_user")
            if isinstance(telegram_user, TelegramUser):
                repository = UserRepository(session)
                db_user = await repository.get_or_create_from_telegram(
                    telegram_user,
                    default_language=self.default_language,
                )
                data["db_user"] = db_user
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
