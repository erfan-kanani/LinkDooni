from collections.abc import Iterable

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    SwitchInlineQueryChosenChat,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.callbacks import (
    CategoryCallback,
    ConfirmCallback,
    EditLinkCallback,
    ExportCallback,
    ExportScopeCallback,
    LinkCallback,
    MenuCallback,
    PickCategoryCallback,
)
from app.db.models import Category, Link
from app.utils.i18n import MessageCatalog


def category_inline_query(category_id: int | None) -> str:
    return f"دسته:{category_id or 0} "


def _share_to_any_chat(query: str = "") -> SwitchInlineQueryChosenChat:
    return SwitchInlineQueryChosenChat(
        query=query,
        allow_user_chats=True,
        allow_bot_chats=False,
        allow_group_chats=True,
        allow_channel_chats=True,
    )


def main_menu(catalog: MessageCatalog, language: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "inline_browse_label"),
            switch_inline_query_current_chat="",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "inline_share_label"),
            switch_inline_query_chosen_chat=_share_to_any_chat(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"➕ {catalog.t(language, 'menu.add')}",
            callback_data=MenuCallback(action="add").pack(),
        ),
        InlineKeyboardButton(
            text=f"📁 {catalog.t(language, 'menu.categories')}",
            callback_data=MenuCallback(action="categories").pack(),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=f"⭐ {catalog.t(language, 'menu.favorites')}",
            callback_data=MenuCallback(action="favorites").pack(),
        ),
        InlineKeyboardButton(
            text=f"📤 {catalog.t(language, 'menu.export')}",
            callback_data=MenuCallback(action="export").pack(),
        ),
    )
    return builder.as_markup()


def categories_keyboard(
    categories: Iterable[Category],
    catalog: MessageCatalog,
    language: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.row(
            InlineKeyboardButton(
                text=_category_label(category),
                switch_inline_query_current_chat=category_inline_query(category.id),
            ),
            InlineKeyboardButton(
                text="⚙",
                callback_data=CategoryCallback(action="open", category_id=category.id).pack(),
            ),
        )
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "categories.uncategorized"),
            switch_inline_query_current_chat=category_inline_query(None),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "categories.create"),
            callback_data=CategoryCallback(action="create", category_id=0).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "menu.back"),
            callback_data=MenuCallback(action="home").pack(),
        )
    )
    return builder.as_markup()


def category_actions_keyboard(
    category: Category | None,
    links: list[Link],
    catalog: MessageCatalog,
    language: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    _ = links
    if category is not None:
        builder.button(
            text=catalog.t(language, "categories.rename"),
            callback_data=CategoryCallback(action="rename", category_id=category.id),
        )
        builder.button(
            text=catalog.t(language, "categories.delete"),
            callback_data=CategoryCallback(action="delete", category_id=category.id),
        )
    builder.button(
        text=catalog.t(language, "menu.back"),
        callback_data=MenuCallback(action="categories"),
    )
    builder.adjust(1)
    return builder.as_markup()


def after_save_keyboard(
    catalog: MessageCatalog,
    language: str,
    *,
    category_id: int | None,
    saved_link: Link | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if saved_link is not None:
        builder.row(
            InlineKeyboardButton(
                text=catalog.t(language, "links.share_now"),
                switch_inline_query_chosen_chat=_share_to_any_chat(
                    query=f"#{saved_link.id}"
                ),
            )
        )
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "links.view_category"),
            switch_inline_query_current_chat=category_inline_query(category_id),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "links.add_another"),
            callback_data=MenuCallback(action="add").pack(),
        ),
        InlineKeyboardButton(
            text=catalog.t(language, "links.home"),
            callback_data=MenuCallback(action="home").pack(),
        ),
    )
    return builder.as_markup()


def inline_search_keyboard(
    catalog: MessageCatalog,
    language: str,
    *,
    query: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=catalog.t(language, "search.open_inline"),
        switch_inline_query_current_chat=query,
    )
    builder.button(text=catalog.t(language, "menu.back"), callback_data=MenuCallback(action="home"))
    builder.adjust(1)
    return builder.as_markup()


def category_picker_keyboard(
    categories: Iterable[Category],
    catalog: MessageCatalog,
    language: str,
    *,
    purpose: str,
    link_id: int = 0,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(
            text=_category_label(category),
            callback_data=PickCategoryCallback(
                purpose=purpose,
                category_id=category.id,
                link_id=link_id,
            ),
        )
    if purpose == "save":
        builder.button(
            text=catalog.t(language, "categories.create_now"),
            callback_data=CategoryCallback(action="create_for_save", category_id=0),
        )
    builder.button(
        text=catalog.t(language, "categories.uncategorized"),
        callback_data=PickCategoryCallback(purpose=purpose, category_id=0, link_id=link_id),
    )
    builder.button(
        text=catalog.t(language, "menu.cancel"), callback_data=MenuCallback(action="home")
    )
    builder.adjust(1)
    return builder.as_markup()


def link_card_keyboard(link: Link, catalog: MessageCatalog, language: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=catalog.t(language, "links.open"), url=link.url))
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "links.share"),
            switch_inline_query_chosen_chat=_share_to_any_chat(query=f"#{link.id}"),
        )
    )
    favorite_label = "links.unfavorite" if link.is_favorite else "links.favorite"
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, favorite_label),
            callback_data=LinkCallback(action="favorite", link_id=link.id).pack(),
        ),
        InlineKeyboardButton(
            text=catalog.t(language, "links.refresh"),
            callback_data=LinkCallback(action="refresh", link_id=link.id).pack(),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "links.edit"),
            callback_data=LinkCallback(action="edit", link_id=link.id).pack(),
        ),
        InlineKeyboardButton(
            text=catalog.t(language, "links.move"),
            callback_data=LinkCallback(action="move", link_id=link.id).pack(),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "links.delete"),
            callback_data=LinkCallback(action="delete", link_id=link.id).pack(),
        ),
        InlineKeyboardButton(
            text=catalog.t(language, "menu.back"),
            callback_data=CategoryCallback(action="open", category_id=link.category_id or 0).pack(),
        ),
    )
    return builder.as_markup()


def link_edit_keyboard(link: Link, catalog: MessageCatalog, language: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    fields = [
        ("title", "links.edit_title"),
        ("url", "links.edit_url"),
        ("description", "links.edit_description"),
        ("category", "links.edit_category"),
        ("tags", "links.edit_tags"),
        ("note", "links.edit_note"),
    ]
    for field, label_key in fields:
        builder.button(
            text=catalog.t(language, label_key),
            callback_data=EditLinkCallback(link_id=link.id, field=field),
        )
    builder.button(
        text=catalog.t(language, "menu.back"),
        callback_data=LinkCallback(action="view", link_id=link.id),
    )
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def confirm_keyboard(
    entity: str,
    item_id: int,
    catalog: MessageCatalog,
    language: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=catalog.t(language, "confirmations.yes_delete"),
        callback_data=ConfirmCallback(entity=entity, action="delete", item_id=item_id),
    )
    builder.button(
        text=catalog.t(language, "confirmations.no_keep"), callback_data=MenuCallback(action="home")
    )
    builder.adjust(1)
    return builder.as_markup()


def links_list_keyboard(
    links: Iterable[Link],
    catalog: MessageCatalog,
    language: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for link in links:
        builder.button(
            text=_truncate(link.title, 42),
            callback_data=LinkCallback(action="view", link_id=link.id),
        )
    builder.button(text=catalog.t(language, "menu.back"), callback_data=MenuCallback(action="home"))
    builder.adjust(1)
    return builder.as_markup()


def export_scope_keyboard(
    categories: Iterable[Category],
    catalog: MessageCatalog,
    language: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "export.scope_all"),
            callback_data=ExportScopeCallback(mode="all").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "export.scope_favorites"),
            callback_data=ExportScopeCallback(mode="favorites").pack(),
        )
    )
    for category in categories:
        builder.row(
            InlineKeyboardButton(
                text=catalog.t(language, "export.scope_category", name=_category_label(category)),
                callback_data=ExportScopeCallback(mode="category", category_id=category.id).pack(),
            )
        )
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "export.scope_uncategorized"),
            callback_data=ExportScopeCallback(mode="uncategorized").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "menu.cancel"),
            callback_data=MenuCallback(action="home").pack(),
        )
    )
    return builder.as_markup()


def export_format_keyboard(
    catalog: MessageCatalog,
    language: str,
    *,
    mode: str,
    category_id: int = 0,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "export.format_message"),
            callback_data=ExportCallback(
                file_format="message", mode=mode, category_id=category_id
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "export.format_json"),
            callback_data=ExportCallback(
                file_format="json", mode=mode, category_id=category_id
            ).pack(),
        ),
        InlineKeyboardButton(
            text=catalog.t(language, "export.format_csv"),
            callback_data=ExportCallback(
                file_format="csv", mode=mode, category_id=category_id
            ).pack(),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=catalog.t(language, "menu.back"),
            callback_data=MenuCallback(action="export").pack(),
        )
    )
    return builder.as_markup()




def _category_label(category: Category) -> str:
    if category.emoji:
        return f"{category.emoji} {category.name}"
    return category.name


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}…"
