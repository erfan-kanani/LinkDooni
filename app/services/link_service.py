from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Link
from app.db.repositories.links import LinkCreate, LinkRepository
from app.services.metadata_fetcher import MetadataFetcher, MetadataFetchError
from app.services.url_validator import UrlValidationError, URLValidator


@dataclass(slots=True)
class SaveLinksResult:
    saved: list[Link] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)
    metadata_failed: list[str] = field(default_factory=list)


class LinkService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        validator: URLValidator | None = None,
        metadata_fetcher: MetadataFetcher | None = None,
    ) -> None:
        self.links = LinkRepository(session)
        self.validator = validator or URLValidator()
        self.metadata_fetcher = metadata_fetcher or MetadataFetcher(validator=self.validator)

    async def save_urls(
        self,
        *,
        user_id: int,
        raw_urls: list[str],
        category_id: int | None,
    ) -> SaveLinksResult:
        result = SaveLinksResult()
        seen: set[str] = set()
        for raw_url in raw_urls:
            try:
                validated = self.validator.validate(raw_url)
            except UrlValidationError:
                result.invalid.append(raw_url)
                continue

            if validated.normalized_url in seen:
                result.duplicates.append(validated.normalized_url)
                continue
            seen.add(validated.normalized_url)

            if await self.links.find_duplicate(user_id, validated.normalized_url):
                result.duplicates.append(validated.normalized_url)
                continue

            try:
                metadata = await self.metadata_fetcher.fetch(validated.normalized_url)
            except UrlValidationError:
                result.invalid.append(validated.normalized_url)
                continue
            except MetadataFetchError:
                metadata = None
                result.metadata_failed.append(validated.normalized_url)

            canonical_url = metadata.canonical_url if metadata else validated.normalized_url
            title = metadata.title if metadata else self._title_from_url(validated.normalized_url)
            link = await self.links.create(
                LinkCreate(
                    user_id=user_id,
                    category_id=category_id,
                    url=validated.normalized_url,
                    canonical_url=canonical_url,
                    title=title,
                    description=metadata.description if metadata else None,
                    preview_image_url=metadata.preview_image_url if metadata else None,
                    favicon_url=metadata.favicon_url
                    if metadata and metadata.favicon_url
                    else self._favicon_from_url(validated.normalized_url),
                )
            )
            result.saved.append(link)
        return result

    async def refresh_metadata(self, *, user_id: int, link_id: int) -> Link | None:
        link = await self.links.get(link_id, user_id)
        if link is None:
            return None
        metadata = await self.metadata_fetcher.fetch(link.url)
        return await self.links.update_fields(
            link_id,
            user_id,
            canonical_url=metadata.canonical_url,
            title=metadata.title,
            description=metadata.description,
            preview_image_url=metadata.preview_image_url,
            favicon_url=metadata.favicon_url or self._favicon_from_url(link.url),
            last_checked_at=datetime.now(UTC),
        )

    def _title_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc.removeprefix("www.") or url

    def _favicon_from_url(self, url: str) -> str | None:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
