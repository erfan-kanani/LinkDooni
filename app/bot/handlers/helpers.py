from contextlib import suppress
from html import escape
from typing import Any

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, LinkPreviewOptions, Message

from app.db.models import Link, User
from app.utils.i18n import MessageCatalog


def language_from_data(data: dict[str, Any]) -> str:
    user = data.get("db_user")
    if isinstance(user, User):
        return user.language_code
    return "fa"


def catalog_from_data(data: dict[str, Any]) -> MessageCatalog:
    catalog = data["messages"]
    if not isinstance(catalog, MessageCatalog):
        raise TypeError("messages must be a MessageCatalog")
    return catalog


def text(data: dict[str, Any], key: str, **kwargs: object) -> str:
    return catalog_from_data(data).t(language_from_data(data), key, **kwargs)


async def edit_or_answer(
    callback: CallbackQuery,
    body: str,
    *,
    reply_markup: Any = None,
    parse_mode: str | None = None,
    link_preview_options: LinkPreviewOptions | None = None,
) -> None:
    if callback.inline_message_id is not None:
        with suppress(TelegramBadRequest):
            await callback.bot.edit_message_text(
                text=body,
                inline_message_id=callback.inline_message_id,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                link_preview_options=link_preview_options,
            )
        await callback.answer()
        return
    if callback.message is None:
        await callback.answer()
        return
    try:
        await callback.message.edit_text(
            body,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            link_preview_options=link_preview_options,
        )
    except TelegramBadRequest:
        if isinstance(callback.message, Message):
            await callback.message.answer(
                body,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                link_preview_options=link_preview_options,
            )
    await callback.answer()


def format_link_card(link: Link, catalog: MessageCatalog, language: str) -> str:
    parts: list[str] = [
        catalog.t(language, "links.card_title", title=escape(link.title)),
        catalog.t(language, "links.card_url", url=escape(link.url)),
    ]
    description = link.description or link.note
    if description:
        parts.append(
            catalog.t(language, "links.card_description", description=escape(description.strip()))
        )
    if link.tags:
        tags = " ".join(f"#{escape(tag.name)}" for tag in link.tags)
        parts.append(tags)
    return "\n".join(parts)


def link_preview_options(link: Link) -> LinkPreviewOptions:
    return LinkPreviewOptions(is_disabled=False, url=link.url)
