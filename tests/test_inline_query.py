from app.bot.handlers.inline import INLINE_PAGE_SIZE, _thumbnail_url, parse_inline_query
from app.db.models import Link


def test_parse_empty_inline_query_lists_all_links() -> None:
    parsed = parse_inline_query("", "")

    assert parsed.mode == "all"
    assert parsed.offset == 0


def test_parse_category_query() -> None:
    parsed = parse_inline_query("cat:12")

    assert parsed.mode == "category"
    assert parsed.category_id == 12


def test_parse_persian_category_query() -> None:
    parsed = parse_inline_query("دسته:12")

    assert parsed.mode == "category"
    assert parsed.category_id == 12


def test_parse_page_suffix() -> None:
    parsed = parse_inline_query("crm p3")

    assert parsed.mode == "search"
    assert parsed.query == "crm"
    assert parsed.offset == INLINE_PAGE_SIZE * 2


def test_inline_offset_takes_precedence_over_page_suffix() -> None:
    parsed = parse_inline_query("crm p3", str(INLINE_PAGE_SIZE))

    assert parsed.query == "crm p3"
    assert parsed.offset == INLINE_PAGE_SIZE


def test_inline_thumbnail_uses_preview_image_first() -> None:
    link = Link(
        user_id=1,
        url="https://example.com/",
        canonical_url="https://example.com/",
        title="Example",
        preview_image_url="https://cdn.example.com/preview.png",
        favicon_url="https://example.com/favicon.ico",
    )

    assert _thumbnail_url(link) == "https://cdn.example.com/preview.png"


def test_inline_thumbnail_uses_google_png_favicon_fallback() -> None:
    link = Link(
        user_id=1,
        url="https://www.ryanair.com/",
        canonical_url="https://www.ryanair.com/",
        title="Ryanair",
        preview_image_url=None,
        favicon_url="https://assets.ryanair.com/favicon.ico",
    )

    thumbnail = _thumbnail_url(link)

    assert thumbnail is not None
    assert thumbnail.startswith("https://t3.gstatic.com/faviconV2?")
    assert "www.ryanair.com" in thumbnail
