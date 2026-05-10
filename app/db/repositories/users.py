from aiogram.types import User as TelegramUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_telegram_id(self, telegram_user_id: int) -> User | None:
        statement = select(User).where(User.telegram_user_id == telegram_user_id)
        return await self.session.scalar(statement)

    async def get_or_create_from_telegram(
        self, telegram_user: TelegramUser, *, default_language: str = "fa"
    ) -> User:
        user = await self.get_by_telegram_id(telegram_user.id)
        language_code = telegram_user.language_code or default_language
        if user is None:
            user = User(
                telegram_user_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                language_code=language_code,
            )
            self.session.add(user)
            await self.session.flush()
            return user

        user.username = telegram_user.username
        user.first_name = telegram_user.first_name
        if not user.language_code:
            user.language_code = language_code
        await self.session.flush()
        return user

    async def set_language(self, user_id: int, language_code: str) -> User | None:
        user = await self.get_by_id(user_id)
        if user is None:
            return None
        user.language_code = language_code
        await self.session.flush()
        return user
