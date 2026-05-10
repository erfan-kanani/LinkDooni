import pytest
from app.services.url_validator import UrlValidationError, URLValidator


def test_extracts_multiple_urls() -> None:
    validator = URLValidator()

    urls = validator.extract_urls("Check https://example.com/a?q=1 and www.example.org/path.")

    assert urls == ["https://example.com/a?q=1", "www.example.org/path"]


def test_normalizes_public_url() -> None:
    validator = URLValidator()

    validated = validator.validate("HTTPS://Example.com:443/path#section")

    assert validated.normalized_url == "https://example.com/path"


def test_adds_https_for_www_url() -> None:
    validator = URLValidator()

    validated = validator.validate("www.example.com")

    assert validated.normalized_url == "https://www.example.com/"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com",
        "http://localhost",
        "http://127.0.0.1",
        "http://10.0.0.4",
        "http://service",
        "http://printer.local",
    ],
)
def test_blocks_unsafe_urls(url: str) -> None:
    validator = URLValidator()

    with pytest.raises(UrlValidationError):
        validator.validate(url)


async def test_blocks_private_dns_resolution() -> None:
    async def resolver(host: str, port: int) -> list[str]:
        assert host == "example.com"
        assert port == 80
        return ["192.168.1.10"]

    validator = URLValidator(resolver=resolver)

    with pytest.raises(UrlValidationError) as exc_info:
        await validator.validate_for_fetch("http://example.com")

    assert exc_info.value.code == "private_host"
