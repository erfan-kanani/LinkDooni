import httpx
import pytest
from app.services.metadata_fetcher import MetadataFetcher, MetadataFetchError
from app.services.url_validator import UrlValidationError, URLValidator


async def public_resolver(host: str, port: int) -> list[str]:
    return ["93.184.216.34"]


async def test_fetches_html_metadata() -> None:
    html = """
    <html>
      <head>
        <title>Fallback Title</title>
        <link rel="canonical" href="https://example.com/canonical">
        <link rel="icon" href="/favicon.png">
        <meta property="og:title" content="Open Graph Title">
        <meta name="description" content="Useful description">
        <meta property="og:image" content="/preview.jpg">
      </head>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://example.com/"
        return httpx.Response(200, headers={"content-type": "text/html"}, text=html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = MetadataFetcher(
            client=client,
            validator=URLValidator(resolver=public_resolver),
        )
        metadata = await fetcher.fetch("https://example.com")

    assert metadata.title == "Open Graph Title"
    assert metadata.description == "Useful description"
    assert metadata.canonical_url == "https://example.com/canonical"
    assert metadata.preview_image_url == "https://example.com/preview.jpg"
    assert metadata.favicon_url == "https://example.com/favicon.png"


async def test_blocks_unsafe_redirect() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = MetadataFetcher(
            client=client,
            validator=URLValidator(resolver=public_resolver),
        )
        with pytest.raises(UrlValidationError):
            await fetcher.fetch("https://example.com")


async def test_treats_captcha_redirect_as_metadata_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(307, headers={"location": "/sttc/px/captcha-v2/index.html"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = MetadataFetcher(
            client=client,
            validator=URLValidator(resolver=public_resolver),
        )
        with pytest.raises(MetadataFetchError) as exc_info:
            await fetcher.fetch("https://example.com")

    assert exc_info.value.code == "blocked_by_site"


async def test_truncates_oversized_response_and_parses_head() -> None:
    head = (
        b"<html><head>"
        b"<meta property=\"og:title\" content=\"Hello\"/>"
        b"</head><body>"
    )
    body = b"x" * 5_000

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=head + body,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = MetadataFetcher(
            client=client,
            validator=URLValidator(resolver=public_resolver),
            max_response_bytes=len(head) + 100,
        )
        metadata = await fetcher.fetch("https://example.com")

    assert metadata.title == "Hello"
