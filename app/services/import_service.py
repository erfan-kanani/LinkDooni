import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.categories import CategoryRepository
from app.db.repositories.links import LinkCreate, LinkRepository
from app.services.url_validator import UrlValidationError, URLValidator


@dataclass(frozen=True, slots=True)
class ImportResult:
    created: int
    skipped: int


class ImportService:
    def __init__(self, session: AsyncSession, validator: URLValidator | None = None) -> None:
        self.categories = CategoryRepository(session)
        self.links = LinkRepository(session)
        self.validator = validator or URLValidator()

    async def import_json(self, user_id: int, raw: str | bytes) -> ImportResult:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return ImportResult(created=0, skipped=0)

        category_ids = await self._ensure_categories(user_id, data.get("categories", []))
        created = 0
        skipped = 0
        for item in data.get("links", []):
            if not isinstance(item, dict):
                skipped += 1
                continue
            try:
                canonical = self.validator.canonicalize(
                    str(item.get("canonical_url") or item["url"])
                )
                url = self.validator.canonicalize(str(item["url"]))
            except (KeyError, UrlValidationError):
                skipped += 1
                continue
            if await self.links.find_duplicate(user_id, canonical):
                skipped += 1
                continue

            category_name = item.get("category")
            await self.links.create(
                LinkCreate(
                    user_id=user_id,
                    category_id=category_ids.get(category_name),
                    url=url,
                    canonical_url=canonical,
                    title=str(item.get("title") or url),
                    description=self._optional_str(item.get("description")),
                    preview_image_url=self._optional_str(item.get("preview_image_url")),
                    favicon_url=self._optional_str(item.get("favicon_url")),
                    note=self._optional_str(item.get("note")),
                    tags=self._string_list(item.get("tags")),
                )
            )
            created += 1

        return ImportResult(created=created, skipped=skipped)

    async def _ensure_categories(self, user_id: int, raw_categories: Any) -> dict[str, int]:
        category_ids: dict[str, int] = {}
        if not isinstance(raw_categories, list):
            return category_ids

        for item in raw_categories:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            name = str(item["name"]).strip()
            category = await self.categories.get_by_name(user_id, name)
            if category is None:
                category = await self.categories.create(
                    user_id,
                    name,
                    emoji=self._optional_str(item.get("emoji")),
                    description=self._optional_str(item.get("description")),
                )
            category_ids[name] = category.id
        return category_ids

    def _optional_str(self, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
