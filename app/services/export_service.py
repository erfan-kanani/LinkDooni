import csv
import io
import json
from dataclasses import dataclass
from html import escape
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Link
from app.db.repositories.categories import CategoryRepository
from app.db.repositories.links import LinkRepository

ExportMode = Literal["all", "favorites", "category", "uncategorized"]
EXPORT_LIMIT = 100_000
TELEGRAM_MESSAGE_LIMIT = 4000


@dataclass(frozen=True, slots=True)
class ExportScope:
    mode: ExportMode = "all"
    category_id: int | None = None


class ExportService:
    def __init__(self, session: AsyncSession) -> None:
        self.categories = CategoryRepository(session)
        self.links = LinkRepository(session)

    async def export_json(self, user_id: int, scope: ExportScope) -> bytes:
        payload = await self._payload(user_id, scope)
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

    async def export_message(
        self,
        user_id: int,
        scope: ExportScope,
        *,
        title: str,
        empty_text: str,
        truncated_template: str,
    ) -> str:
        links = await self._fetch_links(user_id, scope)
        if not links:
            return empty_text
        header = f"📚 <b>{escape(title)}</b>\n<i>{len(links)} لینک</i>\n\n"
        body_parts: list[str] = []
        used = len(header)
        included = 0
        for link in links:
            block = self._link_message_block(link)
            if used + len(block) + 200 > TELEGRAM_MESSAGE_LIMIT:
                break
            body_parts.append(block)
            used += len(block)
            included += 1
        body = "\n".join(body_parts)
        result = header + body
        remaining = len(links) - included
        if remaining > 0:
            result += truncated_template.format(remaining=remaining)
        return result

    def _link_message_block(self, link: Link) -> str:
        title = escape(link.title or link.url)
        url = escape(link.url)
        line = f"🔗 <b>{title}</b>\n{url}"
        if link.description:
            description = escape(link.description.strip())
            if len(description) > 140:
                description = description[:137] + "…"
            line += f"\n<i>{description}</i>"
        if link.tags:
            tags = " ".join(f"#{escape(tag.name)}" for tag in link.tags)
            line += f"\n{tags}"
        return line + "\n"

    async def export_csv(self, user_id: int, scope: ExportScope) -> bytes:
        links = await self._fetch_links(user_id, scope)
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=[
                "url",
                "canonical_url",
                "title",
                "description",
                "category",
                "tags",
                "note",
                "is_favorite",
                "created_at",
            ],
        )
        writer.writeheader()
        for link in links:
            writer.writerow(self._link_csv(link))
        return buffer.getvalue().encode("utf-8-sig")

    async def _fetch_links(self, user_id: int, scope: ExportScope) -> list[Link]:
        if scope.mode == "favorites":
            return await self.links.list_favorites(user_id, limit=EXPORT_LIMIT, offset=0)
        if scope.mode == "category":
            return await self.links.list_by_category(
                user_id, scope.category_id, limit=EXPORT_LIMIT, offset=0
            )
        if scope.mode == "uncategorized":
            return await self.links.list_by_category(
                user_id, None, limit=EXPORT_LIMIT, offset=0
            )
        return await self.links.list_for_user(user_id, limit=EXPORT_LIMIT, offset=0)

    async def _payload(self, user_id: int, scope: ExportScope) -> dict[str, Any]:
        categories = await self.categories.list_for_user(user_id)
        links = await self._fetch_links(user_id, scope)
        return {
            "version": 1,
            "scope": {"mode": scope.mode, "category_id": scope.category_id},
            "categories": [
                {
                    "name": category.name,
                    "emoji": category.emoji,
                    "description": category.description,
                    "sort_order": category.sort_order,
                }
                for category in categories
            ],
            "links": [self._link_json(link) for link in links],
        }

    def _link_json(self, link: Link) -> dict[str, Any]:
        return {
            "url": link.url,
            "canonical_url": link.canonical_url,
            "title": link.title,
            "description": link.description,
            "preview_image_url": link.preview_image_url,
            "favicon_url": link.favicon_url,
            "category": link.category.name if link.category else None,
            "tags": [tag.name for tag in link.tags],
            "note": link.note,
            "is_favorite": link.is_favorite,
            "created_at": link.created_at.isoformat() if link.created_at else None,
        }

    def _link_csv(self, link: Link) -> dict[str, object]:
        return {
            "url": link.url,
            "canonical_url": link.canonical_url,
            "title": link.title,
            "description": link.description or "",
            "category": link.category.name if link.category else "",
            "tags": ", ".join(tag.name for tag in link.tags),
            "note": link.note or "",
            "is_favorite": link.is_favorite,
            "created_at": link.created_at.isoformat() if link.created_at else "",
        }
