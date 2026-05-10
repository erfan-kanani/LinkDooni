from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LinkTag, Tag


class TagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_name(self, user_id: int, name: str) -> Tag | None:
        statement = select(Tag).where(Tag.user_id == user_id, Tag.name == name)
        return await self.session.scalar(statement)

    async def get_or_create_many(self, user_id: int, tag_names: list[str]) -> list[Tag]:
        normalized = []
        for tag_name in tag_names:
            cleaned = tag_name.strip().strip("#").lower()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)

        tags: list[Tag] = []
        for name in normalized:
            tag = await self.get_by_name(user_id, name)
            if tag is None:
                tag = Tag(user_id=user_id, name=name)
                self.session.add(tag)
                await self.session.flush()
            tags.append(tag)
        return tags

    async def replace_link_tags(
        self, link_id: int, user_id: int, tag_names: list[str]
    ) -> list[Tag]:
        tags = await self.get_or_create_many(user_id, tag_names)
        await self.session.execute(delete(LinkTag).where(LinkTag.link_id == link_id))
        for tag in tags:
            self.session.add(LinkTag(link_id=link_id, tag_id=tag.id))
        await self.session.flush()
        return tags
