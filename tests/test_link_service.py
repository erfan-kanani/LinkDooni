from app.db.models import User
from app.services.link_service import LinkService
from app.services.metadata_fetcher import LinkMetadata
from app.services.url_validator import URLValidator
from sqlalchemy.ext.asyncio import AsyncSession


class FakeMetadataFetcher:
    async def fetch(self, url: str) -> LinkMetadata:
        return LinkMetadata(
            url=url,
            canonical_url=url,
            title=f"Title for {url}",
            description="Fetched description",
            preview_image_url=f"{url.rstrip('/')}/preview.png",
            favicon_url=f"{url.rstrip('/')}/favicon.ico",
        )


class RedirectingMetadataFetcher:
    async def fetch(self, url: str) -> LinkMetadata:
        return LinkMetadata(
            url=f"{url.rstrip('/')}/captcha",
            canonical_url=f"{url.rstrip('/')}/canonical",
            title="Fetched title",
            description="Fetched description",
            preview_image_url=None,
            favicon_url=None,
        )


class CanonicalCollisionMetadataFetcher:
    async def fetch(self, url: str) -> LinkMetadata:
        return LinkMetadata(
            url=url,
            canonical_url="https://example.com/localized",
            title=f"Title for {url}",
        )


async def test_save_urls_flow_detects_duplicates(session: AsyncSession) -> None:
    user = User(telegram_user_id=3003, username="team", first_name="Team", language_code="fa")
    session.add(user)
    await session.flush()

    service = LinkService(
        session,
        validator=URLValidator(),
        metadata_fetcher=FakeMetadataFetcher(),  # type: ignore[arg-type]
    )
    result = await service.save_urls(
        user_id=user.id,
        raw_urls=["https://example.com", "https://example.com/"],
        category_id=None,
    )

    assert len(result.saved) == 1
    assert result.saved[0].title == "Title for https://example.com/"
    assert result.duplicates == ["https://example.com/"]


async def test_save_keeps_original_url_when_metadata_redirects(session: AsyncSession) -> None:
    user = User(telegram_user_id=4004, username="team2", first_name="Team", language_code="fa")
    session.add(user)
    await session.flush()

    service = LinkService(
        session,
        validator=URLValidator(),
        metadata_fetcher=RedirectingMetadataFetcher(),  # type: ignore[arg-type]
    )
    result = await service.save_urls(
        user_id=user.id,
        raw_urls=["https://example.com"],
        category_id=None,
    )

    assert len(result.saved) == 1
    assert result.saved[0].url == "https://example.com/"
    assert result.saved[0].canonical_url == "https://example.com/canonical"
    assert result.saved[0].favicon_url == "https://example.com/favicon.ico"


async def test_save_allows_different_original_urls_with_same_canonical(
    session: AsyncSession,
) -> None:
    user = User(telegram_user_id=5005, username="team3", first_name="Team", language_code="fa")
    session.add(user)
    await session.flush()

    service = LinkService(
        session,
        validator=URLValidator(),
        metadata_fetcher=CanonicalCollisionMetadataFetcher(),  # type: ignore[arg-type]
    )
    first = await service.save_urls(
        user_id=user.id,
        raw_urls=["https://example.com/localized"],
        category_id=None,
    )
    second = await service.save_urls(
        user_id=user.id,
        raw_urls=["https://example.com/"],
        category_id=None,
    )

    assert len(first.saved) == 1
    assert len(second.saved) == 1
    assert second.duplicates == []
