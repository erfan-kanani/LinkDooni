from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Category, Link, Tag
from app.db.repositories.tags import TagRepository
from app.utils.persian import normalize_persian, normalize_persian_sql


@dataclass(slots=True)
class LinkCreate:
    user_id: int
    url: str
    canonical_url: str
    title: str
    category_id: int | None = None
    description: str | None = None
    preview_image_url: str | None = None
    favicon_url: str | None = None
    note: str | None = None
    tags: list[str] | None = None


class LinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tags = TagRepository(session)

    async def get(self, link_id: int, user_id: int) -> Link | None:
        statement = self._base_select().where(Link.id == link_id, Link.user_id == user_id)
        return await self.session.scalar(statement)

    async def find_duplicate(self, user_id: int, canonical_url: str) -> Link | None:
        statement = self._base_select().where(
            Link.user_id == user_id,
            Link.url == canonical_url,
        )
        return await self.session.scalar(statement)

    async def create(self, payload: LinkCreate) -> Link:
        link = Link(
            user_id=payload.user_id,
            category_id=payload.category_id,
            url=payload.url,
            canonical_url=payload.canonical_url,
            title=payload.title[:500] or payload.url,
            description=payload.description,
            preview_image_url=payload.preview_image_url,
            favicon_url=payload.favicon_url,
            note=payload.note,
            last_checked_at=datetime.now(UTC),
        )
        self.session.add(link)
        await self.session.flush()
        if payload.tags:
            await self.tags.replace_link_tags(link.id, payload.user_id, payload.tags)
        return await self.get(link.id, payload.user_id) or link

    async def update_fields(self, link_id: int, user_id: int, **fields: Any) -> Link | None:
        tags = fields.pop("tags", None)
        link = await self.get(link_id, user_id)
        if link is None:
            return None
        allowed = {
            "category_id",
            "url",
            "canonical_url",
            "title",
            "description",
            "preview_image_url",
            "favicon_url",
            "note",
            "is_favorite",
            "last_checked_at",
        }
        for key, value in fields.items():
            if key in allowed:
                setattr(link, key, value)
        await self.session.flush()
        if tags is not None:
            await self.tags.replace_link_tags(link.id, user_id, list(tags))
        return await self.get(link.id, user_id)

    async def delete(self, link_id: int, user_id: int) -> bool:
        link = await self.get(link_id, user_id)
        if link is None:
            return False
        await self.session.delete(link)
        await self.session.flush()
        return True

    async def list_by_category(
        self, user_id: int, category_id: int | None, *, limit: int = 10, offset: int = 0
    ) -> list[Link]:
        statement = self._base_select().where(Link.user_id == user_id)
        if category_id is None:
            statement = statement.where(Link.category_id.is_(None))
        else:
            statement = statement.where(Link.category_id == category_id)
        statement = (
            statement.order_by(Link.is_favorite.desc(), Link.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(await self.session.scalars(statement))

    async def list_favorites(self, user_id: int, *, limit: int = 20, offset: int = 0) -> list[Link]:
        statement = (
            self._base_select()
            .where(Link.user_id == user_id, Link.is_favorite.is_(True))
            .order_by(Link.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(await self.session.scalars(statement))

    async def list_for_user(
        self, user_id: int, *, limit: int = 1000, offset: int = 0
    ) -> list[Link]:
        statement = (
            self._base_select()
            .where(Link.user_id == user_id)
            .order_by(Link.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(await self.session.scalars(statement))

    async def search(
        self, user_id: int, query: str, *, limit: int = 20, offset: int = 0
    ) -> list[Link]:
        normalized = normalize_persian(query)
        if not normalized:
            return []
        pattern = f"%{normalized}%"
        statement = (
            self._base_select()
            .outerjoin(Link.category)
            .outerjoin(Link.tags)
            .where(Link.user_id == user_id)
            .where(
                or_(
                    normalize_persian_sql(Link.title).like(pattern),
                    normalize_persian_sql(Link.url).like(pattern),
                    normalize_persian_sql(Link.canonical_url).like(pattern),
                    normalize_persian_sql(func.coalesce(Link.description, "")).like(pattern),
                    normalize_persian_sql(func.coalesce(Link.note, "")).like(pattern),
                    normalize_persian_sql(func.coalesce(Category.name, "")).like(pattern),
                    normalize_persian_sql(func.coalesce(Tag.name, "")).like(pattern),
                )
            )
            .distinct()
            .order_by(Link.is_favorite.desc(), Link.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.scalars(statement)
        return list(result.unique())

    def _base_select(self) -> Select[tuple[Link]]:
        return select(Link).options(selectinload(Link.category), selectinload(Link.tags))
