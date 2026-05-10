import re
from dataclasses import dataclass
from html import escape
from typing import Any, Literal
from urllib.parse import quote, urlparse

from aiogram import Router
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    LinkPreviewOptions,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.helpers import catalog_from_data, format_link_card, language_from_data, text
from app.bot.keyboards.builders import link_card_keyboard
from app.db.models import Link, User
from app.db.repositories.links import LinkRepository

router = Router(name="inline")

INLINE_PAGE_SIZE = 50
PAGE_PATTERN = re.compile(r"(?:^|\s)p(?P<page>\d+)\s*$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class InlineLinkQuery:
    mode: Literal["all", "category", "favorites", "search"]
    query: str
    category_id: int | None
    page: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * INLINE_PAGE_SIZE


@router.inline_query()
async def inline_links_query(
    inline_query: InlineQuery,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    parsed = parse_inline_query(inline_query.query, inline_query.offset)
    links, has_next_page = await _load_links(session, db_user.id, parsed)
    results = [_link_result(link, data, parsed.offset) for link in links]
    if not results:
        results = [_empty_result(data)]

    await inline_query.answer(
        results,
        cache_time=1,
        is_personal=True,
        next_offset=str(parsed.offset + INLINE_PAGE_SIZE) if has_next_page else "",
    )


def parse_inline_query(raw_query: str, raw_offset: str | None = None) -> InlineLinkQuery:
    query = raw_query.strip()
    page = _page_from_offset(raw_offset)
    page_match = PAGE_PATTERN.search(query)
    if page_match and page == 1:
        page = max(int(page_match.group("page")), 1)
        query = query[: page_match.start()].strip()

    lower_query = query.lower()
    if lower_query in {"fav", "favorite", "favorites"}:
        return InlineLinkQuery("favorites", "", None, page)
    category_value = _category_value(lower_query)
    if category_value is not None:
        try:
            category_id = int(category_value or "0")
        except ValueError:
            category_id = 0
        return InlineLinkQuery("category", "", category_id or None, page)
    if not query:
        return InlineLinkQuery("all", "", None, page)
    return InlineLinkQuery("search", query, None, page)


def _category_value(query: str) -> str | None:
    for prefix in ("cat:", "category:", "دسته:"):
        if query.startswith(prefix):
            return query.removeprefix(prefix).strip()
    return None


async def _load_links(
    session: AsyncSession,
    user_id: int,
    parsed: InlineLinkQuery,
) -> tuple[list[Link], bool]:
    repository = LinkRepository(session)
    limit = INLINE_PAGE_SIZE + 1
    if parsed.mode == "category":
        links = await repository.list_by_category(
            user_id,
            parsed.category_id,
            limit=limit,
            offset=parsed.offset,
        )
    elif parsed.mode == "favorites":
        links = await repository.list_favorites(
            user_id,
            limit=limit,
            offset=parsed.offset,
        )
    elif parsed.mode == "search":
        links = await repository.search(
            user_id,
            parsed.query,
            limit=limit,
            offset=parsed.offset,
        )
    else:
        links = await repository.list_for_user(user_id, limit=limit, offset=parsed.offset)
    return links[:INLINE_PAGE_SIZE], len(links) > INLINE_PAGE_SIZE


def _link_result(
    link: Link,
    data: dict[str, Any],
    offset: int,
) -> InlineQueryResultArticle:
    catalog = catalog_from_data(data)
    language = language_from_data(data)
    description_parts = [
        link.category.name if link.category else catalog.t(language, "categories.uncategorized"),
        link.description or link.url,
    ]
    version = int(link.updated_at.timestamp()) if link.updated_at else 0
    return InlineQueryResultArticle(
        id=f"link:v2:{link.id}:{version}:{offset}",
        title=link.title,
        description=" · ".join(part for part in description_parts if part),
        thumbnail_url=_thumbnail_url(link),
        thumbnail_width=128,
        thumbnail_height=128,
        input_message_content=InputTextMessageContent(
            message_text=format_link_card(link, catalog, language),
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(
                is_disabled=False,
                url=link.url,
                prefer_large_media=bool(link.preview_image_url),
            ),
        ),
        reply_markup=link_card_keyboard(link, catalog, language),
    )


def _thumbnail_url(link: Link) -> str | None:
    if link.preview_image_url:
        return link.preview_image_url
    parsed = urlparse(link.url)
    if not parsed.netloc:
        return link.favicon_url
    domain = parsed.netloc.lower()
    site_url = f"https://{domain}"
    return (
        "https://t3.gstatic.com/faviconV2"
        "?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL"
        f"&size=128&url={quote(site_url, safe='')}"
    )


def _empty_result(data: dict[str, Any]) -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id="empty",
        title=text(data, "inline.empty_title"),
        description=text(data, "inline.empty_description"),
        input_message_content=InputTextMessageContent(
            message_text=escape(text(data, "inline.empty_description")),
            parse_mode="HTML",
        ),
    )


def _page_from_offset(raw_offset: str | None) -> int:
    if not raw_offset:
        return 1
    try:
        offset = max(int(raw_offset), 0)
    except ValueError:
        return 1
    return (offset // INLINE_PAGE_SIZE) + 1
