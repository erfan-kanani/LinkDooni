from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser

from app.services.url_validator import UrlValidationError, URLValidator


class MetadataFetchError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class LinkMetadata:
    url: str
    canonical_url: str
    title: str
    description: str | None = None
    preview_image_url: str | None = None
    favicon_url: str | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class MetadataFetcher:
    protection_path_markers = (
        "captcha",
        "challenge",
        "checkpoint",
        "verify",
        "/cdn-cgi/",
        "bot-protection",
        "bot_management",
    )

    def __init__(
        self,
        *,
        validator: URLValidator | None = None,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 8.0,
        max_response_bytes: int = 1_500_000,
        max_redirects: int = 5,
    ) -> None:
        self.validator = validator or URLValidator()
        self.client = client
        self.timeout = httpx.Timeout(timeout_seconds)
        self.max_response_bytes = max_response_bytes
        self.max_redirects = max_redirects

    async def fetch(self, url: str) -> LinkMetadata:
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient()
        try:
            return await self._fetch_with_client(client, url)
        finally:
            if owns_client:
                await client.aclose()

    async def _fetch_with_client(self, client: httpx.AsyncClient, url: str) -> LinkMetadata:
        current = await self.validator.validate_for_fetch(url)
        redirects = 0

        while True:
            try:
                response = await self._request(client, current.normalized_url)
            except httpx.TimeoutException as exc:
                raise MetadataFetchError("timeout", "Website did not respond in time.") from exc
            except httpx.HTTPError as exc:
                raise MetadataFetchError("http_error", str(exc)) from exc

            if response.is_redirect:
                if redirects >= self.max_redirects:
                    raise MetadataFetchError("too_many_redirects", "Too many redirects.")
                location = response.headers.get("location")
                if not location:
                    raise MetadataFetchError("bad_redirect", "Redirect response had no location.")
                redirected_url = urljoin(current.normalized_url, location)
                if self._is_protection_url(redirected_url):
                    raise MetadataFetchError(
                        "blocked_by_site",
                        "Website redirected metadata fetch to a protection page.",
                    )
                current = await self.validator.validate_for_fetch(redirected_url)
                redirects += 1
                continue

            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                return self._fallback_metadata(current.normalized_url)

            text = response.content.decode(response.encoding or "utf-8", errors="replace")
            return self._parse_html(current.normalized_url, text)

    async def _request(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        headers = {
            "accept": "text/html,application/xhtml+xml",
            "user-agent": "TelegramBot (like TwitterBot)",
        }
        async with client.stream(
            "GET",
            url,
            headers=headers,
            follow_redirects=False,
            timeout=self.timeout,
        ) as response:
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                chunks.append(chunk)
                total += len(chunk)
                if total >= self.max_response_bytes:
                    break
            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                content=b"".join(chunks),
                request=response.request,
                extensions=response.extensions,
            )

    def _parse_html(self, final_url: str, html: str) -> LinkMetadata:
        if self._is_protection_url(final_url):
            raise MetadataFetchError(
                "blocked_by_site",
                "Website returned a protection page instead of metadata.",
            )

        tree = HTMLParser(html)
        canonical = self._absolute_url(final_url, self._link_href(tree, "canonical")) or final_url
        try:
            canonical = self.validator.canonicalize(canonical)
        except UrlValidationError:
            canonical = final_url

        title = (
            self._meta_content(tree, "og:title")
            or self._meta_content(tree, "twitter:title")
            or self._title_text(tree)
            or urlparse(final_url).netloc
        )
        description = (
            self._meta_content(tree, "og:description")
            or self._meta_content(tree, "description")
            or self._meta_content(tree, "twitter:description")
        )
        image = self._absolute_url(
            final_url,
            self._meta_content(tree, "og:image") or self._meta_content(tree, "twitter:image"),
        )
        favicon = self._absolute_url(final_url, self._icon_href(tree)) or self._absolute_url(
            final_url, "/favicon.ico"
        )

        return LinkMetadata(
            url=final_url,
            canonical_url=canonical,
            title=self._squash(title),
            description=self._squash(description) if description else None,
            preview_image_url=image,
            favicon_url=favicon,
            fetched_at=datetime.now(UTC),
        )

    def _fallback_metadata(self, url: str) -> LinkMetadata:
        return LinkMetadata(
            url=url,
            canonical_url=url,
            title=urlparse(url).netloc or url,
            favicon_url=self._default_favicon_url(url),
            fetched_at=datetime.now(UTC),
        )

    def _meta_content(self, tree: HTMLParser, key: str) -> str | None:
        tag = tree.css_first(f'meta[property="{key}"]') or tree.css_first(f'meta[name="{key}"]')
        content = tag.attributes.get("content") if tag else None
        return content.strip() if content else None

    def _link_href(self, tree: HTMLParser, rel: str) -> str | None:
        for tag in tree.css("link"):
            rel_value = tag.attributes.get("rel", "")
            if rel in rel_value.lower().split():
                href = tag.attributes.get("href")
                return href.strip() if href else None
        return None

    def _icon_href(self, tree: HTMLParser) -> str | None:
        for tag in tree.css("link"):
            rel_value = tag.attributes.get("rel", "")
            if "icon" in rel_value.lower():
                href = tag.attributes.get("href")
                return href.strip() if href else None
        return None

    def _title_text(self, tree: HTMLParser) -> str | None:
        title = tree.css_first("title")
        if title is None:
            return None
        return title.text(strip=True)

    def _absolute_url(self, base_url: str, maybe_url: str | None) -> str | None:
        if not maybe_url:
            return None
        candidate = urljoin(base_url, maybe_url)
        try:
            return self.validator.validate(candidate).normalized_url
        except UrlValidationError:
            return None

    def _squash(self, value: str) -> str:
        return " ".join(value.split())

    def _default_favicon_url(self, url: str) -> str | None:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"

    def _is_protection_url(self, url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path.lower()
        return any(marker in path for marker in self.protection_path_markers)
