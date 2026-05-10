import csv
import io
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Link
from app.db.repositories.categories import CategoryRepository
from app.db.repositories.links import LinkRepository


class ExportService:
    def __init__(self, session: AsyncSession) -> None:
        self.categories = CategoryRepository(session)
        self.links = LinkRepository(session)

    async def export_json(self, user_id: int) -> bytes:
        payload = await self._payload(user_id)
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

    async def export_csv(self, user_id: int) -> bytes:
        links = await self.links.list_for_user(user_id)
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

    async def _payload(self, user_id: int) -> dict[str, Any]:
        categories = await self.categories.list_for_user(user_id)
        links = await self.links.list_for_user(user_id)
        return {
            "version": 1,
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
