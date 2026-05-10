from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Category, Link


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, category_id: int, user_id: int) -> Category | None:
        statement = select(Category).where(Category.id == category_id, Category.user_id == user_id)
        return await self.session.scalar(statement)

    async def get_by_name(self, user_id: int, name: str) -> Category | None:
        statement = select(Category).where(Category.user_id == user_id, Category.name == name)
        return await self.session.scalar(statement)

    async def list_for_user(self, user_id: int) -> list[Category]:
        statement = (
            select(Category)
            .where(Category.user_id == user_id)
            .order_by(Category.sort_order, Category.name)
        )
        return list(await self.session.scalars(statement))

    async def create(
        self,
        user_id: int,
        name: str,
        *,
        emoji: str | None = None,
        description: str | None = None,
    ) -> Category:
        categories = await self.list_for_user(user_id)
        category = Category(
            user_id=user_id,
            name=name.strip(),
            emoji=emoji,
            description=description,
            sort_order=len(categories),
        )
        self.session.add(category)
        await self.session.flush()
        return category

    async def rename(self, category_id: int, user_id: int, name: str) -> Category | None:
        category = await self.get(category_id, user_id)
        if category is None:
            return None
        category.name = name.strip()
        await self.session.flush()
        return category

    async def delete(self, category_id: int, user_id: int) -> bool:
        category = await self.get(category_id, user_id)
        if category is None:
            return False
        await self.session.execute(
            update(Link)
            .where(Link.category_id == category.id, Link.user_id == user_id)
            .values(category_id=None)
        )
        await self.session.delete(category)
        await self.session.flush()
        return True
