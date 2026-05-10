import asyncio
import ipaddress
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final
from urllib.parse import ParseResult, urlparse, urlunparse

URL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?P<url>(?:https?://|www\.)[^\s<>\]\[()\"']+)",
    re.IGNORECASE,
)


class UrlValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ValidatedUrl:
    original_url: str
    normalized_url: str
    parsed: ParseResult


HostResolver = Callable[[str, int], Awaitable[list[str]]]


class URLValidator:
    blocked_suffixes: Final[tuple[str, ...]] = (
        ".localhost",
        ".local",
        ".internal",
        ".lan",
        ".home",
    )

    def __init__(self, resolver: HostResolver | None = None) -> None:
        self.resolver = resolver or self._default_resolver

    def extract_urls(self, text: str | None) -> list[str]:
        if not text:
            return []
        urls: list[str] = []
        for match in URL_PATTERN.finditer(text):
            candidate = match.group("url").rstrip(".,;:!?،؛)")
            if candidate not in urls:
                urls.append(candidate)
        return urls

    def validate(self, url: str) -> ValidatedUrl:
        normalized_input = self._with_scheme(url.strip())
        parsed = urlparse(normalized_input)
        if parsed.scheme.lower() not in {"http", "https"}:
            raise UrlValidationError(
                "unsupported_scheme", "Only http and https URLs are supported."
            )
        if not parsed.hostname:
            raise UrlValidationError("invalid_url", "URL host is required.")

        host = self._normalize_host(parsed.hostname)
        self._ensure_safe_hostname(host)

        try:
            port = parsed.port
        except ValueError as exc:
            raise UrlValidationError("invalid_url", "URL port is not valid.") from exc

        display_host = f"[{host}]" if ":" in host else host
        normalized_netloc = display_host
        if port and not self._is_default_port(parsed.scheme, port):
            normalized_netloc = f"{display_host}:{port}"

        path = parsed.path or "/"
        normalized = urlunparse(
            (
                parsed.scheme.lower(),
                normalized_netloc,
                path,
                "",
                parsed.query,
                "",
            )
        )
        return ValidatedUrl(
            original_url=url, normalized_url=normalized, parsed=urlparse(normalized)
        )

    async def validate_for_fetch(self, url: str) -> ValidatedUrl:
        validated = self.validate(url)
        host = validated.parsed.hostname
        if host is None:
            raise UrlValidationError("invalid_url", "URL host is required.")
        port = validated.parsed.port or (443 if validated.parsed.scheme == "https" else 80)
        resolved_ips = await self.resolver(host, port)
        if not resolved_ips:
            raise UrlValidationError("invalid_url", "Host did not resolve.")
        for resolved_ip in resolved_ips:
            self._ensure_public_ip(resolved_ip)
        return validated

    def canonicalize(self, url: str) -> str:
        return self.validate(url).normalized_url

    async def _default_resolver(self, host: str, port: int) -> list[str]:
        loop = asyncio.get_running_loop()
        infos = await loop.getaddrinfo(host, port, type=0, proto=0)
        return sorted({info[4][0] for info in infos})

    def _with_scheme(self, url: str) -> str:
        if url.lower().startswith("www."):
            return f"https://{url}"
        return url

    def _normalize_host(self, host: str) -> str:
        cleaned = host.strip().strip("[]").rstrip(".").lower()
        try:
            return cleaned.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise UrlValidationError("invalid_url", "URL host is not valid.") from exc

    def _ensure_safe_hostname(self, host: str) -> None:
        if host in {"localhost", "0", "0.0.0.0"}:
            raise UrlValidationError("private_host", "Localhost is blocked.")
        if "." not in host and not self._looks_like_ip(host):
            raise UrlValidationError("private_host", "Single-label internal hosts are blocked.")
        if any(host.endswith(suffix) for suffix in self.blocked_suffixes):
            raise UrlValidationError("private_host", "Internal hostnames are blocked.")
        if self._looks_like_ip(host):
            self._ensure_public_ip(host)

    def _ensure_public_ip(self, value: str) -> None:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise UrlValidationError("invalid_url", "Resolved address is not valid.") from exc
        if not address.is_global:
            raise UrlValidationError(
                "private_host", "Private, local, and reserved IPs are blocked."
            )

    def _looks_like_ip(self, host: str) -> bool:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return False
        return True

    def _is_default_port(self, scheme: str, port: int) -> bool:
        return (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
