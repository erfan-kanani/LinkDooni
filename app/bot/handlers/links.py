from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, LinkPreviewOptions, Message
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.helpers import (
    catalog_from_data,
    edit_or_answer,
    format_link_card,
    language_from_data,
    link_preview_options,
    text,
)
from app.bot.keyboards.builders import (
    after_save_keyboard,
    category_picker_keyboard,
    confirm_keyboard,
    export_format_keyboard,
    export_scope_keyboard,
    inline_search_keyboard,
    link_card_keyboard,
    link_edit_keyboard,
    links_list_keyboard,
)
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
from app.bot.states.main import LinkStates
from app.config.settings import Settings
from app.db.models import User
from app.db.repositories.categories import CategoryRepository
from app.db.repositories.links import LinkRepository
from app.services.export_service import ExportScope, ExportService
from app.services.link_service import LinkService, SaveLinksResult
from app.services.metadata_fetcher import MetadataFetcher, MetadataFetchError
from app.services.search_service import SearchService
from app.services.url_validator import UrlValidationError, URLValidator

router = Router(name="links")


@router.message(Command("add"))
async def add_command(message: Message, state: FSMContext, **data: Any) -> None:
    await state.set_state(LinkStates.waiting_urls)
    await message.answer(text(data, "links.add_prompt"))


@router.callback_query(MenuCallback.filter(F.action == "add"))
async def add_callback(callback: CallbackQuery, state: FSMContext, **data: Any) -> None:
    await state.set_state(LinkStates.waiting_urls)
    await edit_or_answer(callback, text(data, "links.add_prompt"))


@router.message(LinkStates.waiting_urls)
async def add_urls_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    await collect_urls(message, state, session, db_user, data)


@router.message(
    StateFilter(None),
    (F.text & ~F.text.startswith("/")) | (F.caption & ~F.caption.startswith("/")),
)
async def direct_url_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    if not _message_text(message):
        return
    if message.via_bot is not None and message.via_bot.id == message.bot.id:
        return
    urls = URLValidator().extract_urls(_message_text(message))
    if not urls:
        return
    await ask_for_category(message, state, session, db_user, data, urls)


@router.callback_query(PickCategoryCallback.filter(F.purpose == "save"))
async def save_category_picked(
    callback: CallbackQuery,
    callback_data: PickCategoryCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    state_data = await state.get_data()
    urls = [str(url) for url in state_data.get("pending_urls", [])]
    await state.clear()
    if not urls:
        await callback.answer()
        return
    await save_pending_urls(
        callback,
        session,
        db_user,
        data,
        urls,
        category_id=callback_data.category_id or None,
    )


@router.callback_query(CategoryCallback.filter(F.action == "create_for_save"))
async def create_category_for_save_callback(
    callback: CallbackQuery,
    state: FSMContext,
    **data: Any,
) -> None:
    await state.set_state(LinkStates.waiting_save_category_name)
    await edit_or_answer(callback, text(data, "links.create_category_prompt"))


@router.message(LinkStates.waiting_save_category_name)
async def create_category_for_save_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    category_name = (message.text or "").strip()
    state_data = await state.get_data()
    urls = [str(url) for url in state_data.get("pending_urls", [])]
    if not category_name:
        await message.answer(text(data, "links.create_category_prompt"))
        return
    if not urls:
        await state.clear()
        await message.answer(text(data, "links.add_prompt"))
        return
    categories = CategoryRepository(session)
    category = await categories.get_by_name(db_user.id, category_name)
    if category is None:
        category = await categories.create(db_user.id, category_name)
    await state.clear()
    result = await _link_service(session, data).save_urls(
        user_id=db_user.id,
        raw_urls=urls,
        category_id=category.id,
    )
    saved_link = result.saved[0] if len(result.saved) == 1 else None
    await message.answer(
        _save_summary(result, data),
        reply_markup=after_save_keyboard(
            catalog_from_data(data),
            language_from_data(data),
            category_id=category.id,
            saved_link=saved_link,
        ),
    )


async def save_pending_urls(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    data: dict[str, Any],
    urls: list[str],
    *,
    category_id: int | None,
) -> None:
    service = _link_service(session, data)
    result = await service.save_urls(
        user_id=db_user.id,
        raw_urls=urls,
        category_id=category_id,
    )
    saved_link = result.saved[0] if len(result.saved) == 1 else None
    await edit_or_answer(
        callback,
        _save_summary(result, data),
        reply_markup=after_save_keyboard(
            catalog_from_data(data),
            language_from_data(data),
            category_id=category_id,
            saved_link=saved_link,
        ),
    )


@router.message(Command("search"))
async def search_command(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    if command.args:
        await message.answer(
            text(data, "search.inline_prompt"),
            reply_markup=inline_search_keyboard(
                catalog_from_data(data),
                language_from_data(data),
                query=command.args,
            ),
        )
        return
    await state.set_state(LinkStates.waiting_search)
    await message.answer(text(data, "search.prompt"))


@router.callback_query(MenuCallback.filter(F.action == "search"))
async def search_callback(callback: CallbackQuery, state: FSMContext, **data: Any) -> None:
    await state.set_state(LinkStates.waiting_search)
    await edit_or_answer(callback, text(data, "search.prompt"))


@router.message(LinkStates.waiting_search)
async def search_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    query = (message.text or "").strip()
    await state.clear()
    await message.answer(
        text(data, "search.inline_prompt"),
        reply_markup=inline_search_keyboard(
            catalog_from_data(data),
            language_from_data(data),
            query=query,
        ),
    )


@router.message(Command("favorites"))
async def favorites_command(
    message: Message,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    await send_favorites(message, session, db_user, data)


@router.callback_query(MenuCallback.filter(F.action == "favorites"))
async def favorites_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    links = await LinkRepository(session).list_favorites(db_user.id)
    body = text(data, "menu.favorites") if links else text(data, "search.empty")
    await edit_or_answer(
        callback,
        body,
        reply_markup=links_list_keyboard(links, catalog_from_data(data), language_from_data(data)),
    )


@router.callback_query(LinkCallback.filter(F.action == "view"))
async def link_view_callback(
    callback: CallbackQuery,
    callback_data: LinkCallback,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    link = await LinkRepository(session).get(callback_data.link_id, db_user.id)
    if link is None:
        await callback.answer()
        return
    catalog = catalog_from_data(data)
    language = language_from_data(data)
    await edit_or_answer(
        callback,
        format_link_card(link, catalog, language),
        reply_markup=link_card_keyboard(link, catalog, language),
        parse_mode="HTML",
        link_preview_options=link_preview_options(link),
    )


@router.callback_query(LinkCallback.filter(F.action == "edit"))
async def link_edit_callback(
    callback: CallbackQuery,
    callback_data: LinkCallback,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    link = await LinkRepository(session).get(callback_data.link_id, db_user.id)
    if link is None:
        await callback.answer()
        return
    await edit_or_answer(
        callback,
        text(data, "links.edit_menu"),
        reply_markup=link_edit_keyboard(link, catalog_from_data(data), language_from_data(data)),
    )


@router.callback_query(EditLinkCallback.filter())
async def edit_field_callback(
    callback: CallbackQuery,
    callback_data: EditLinkCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    if callback_data.field == "category":
        categories = await CategoryRepository(session).list_by_recent_use(db_user.id)
        await edit_or_answer(
            callback,
            text(data, "links.choose_category", count=1),
            reply_markup=category_picker_keyboard(
                categories,
                catalog_from_data(data),
                language_from_data(data),
                purpose="editcat",
                link_id=callback_data.link_id,
            ),
        )
        return
    await state.set_state(LinkStates.waiting_edit_value)
    await state.update_data(link_id=callback_data.link_id, field=callback_data.field)
    label = text(data, f"links.edit_{callback_data.field}")
    await edit_or_answer(callback, text(data, "links.edit_prompt", field=label))


@router.message(LinkStates.waiting_edit_value)
async def edit_value_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    state_data = await state.get_data()
    link_id = int(state_data.get("link_id", 0))
    field = str(state_data.get("field", ""))
    value = (message.text or "").strip()
    repository = LinkRepository(session)
    try:
        if field == "url":
            validated = URLValidator().validate(value)
            duplicate = await repository.find_duplicate(db_user.id, validated.normalized_url)
            if duplicate and duplicate.id != link_id:
                await message.answer(text(data, "links.duplicate", url=validated.normalized_url))
                return
            await repository.update_fields(
                link_id,
                db_user.id,
                url=validated.normalized_url,
                canonical_url=validated.normalized_url,
            )
        elif field == "tags":
            await repository.update_fields(
                link_id,
                db_user.id,
                tags=[part.strip() for part in value.split(",")],
            )
        elif field in {"title", "description", "note"}:
            await repository.update_fields(link_id, db_user.id, **{field: value})
        else:
            await message.answer(text(data, "validation.generic"))
            return
    except (UrlValidationError, IntegrityError):
        await message.answer(text(data, "validation.generic"))
        return
    await state.clear()
    await message.answer(text(data, "links.edit_saved"))


@router.callback_query(PickCategoryCallback.filter(F.purpose.in_({"move", "editcat"})))
async def move_or_edit_category_callback(
    callback: CallbackQuery,
    callback_data: PickCategoryCallback,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    link = await LinkRepository(session).update_fields(
        callback_data.link_id,
        db_user.id,
        category_id=callback_data.category_id or None,
    )
    if link is None:
        await callback.answer()
        return
    await edit_or_answer(
        callback,
        text(data, "links.moved"),
        reply_markup=link_card_keyboard(link, catalog_from_data(data), language_from_data(data)),
    )


@router.callback_query(LinkCallback.filter(F.action == "move"))
async def link_move_callback(
    callback: CallbackQuery,
    callback_data: LinkCallback,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    categories = await CategoryRepository(session).list_by_recent_use(db_user.id)
    await edit_or_answer(
        callback,
        text(data, "links.choose_category", count=1),
        reply_markup=category_picker_keyboard(
            categories,
            catalog_from_data(data),
            language_from_data(data),
            purpose="move",
            link_id=callback_data.link_id,
        ),
    )


@router.callback_query(LinkCallback.filter(F.action == "delete"))
async def link_delete_callback(
    callback: CallbackQuery,
    callback_data: LinkCallback,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    link = await LinkRepository(session).get(callback_data.link_id, db_user.id)
    if link is None:
        await callback.answer()
        return
    await edit_or_answer(
        callback,
        text(data, "links.delete_confirm", title=link.title),
        reply_markup=confirm_keyboard(
            "link", link.id, catalog_from_data(data), language_from_data(data)
        ),
    )


@router.callback_query(ConfirmCallback.filter((F.entity == "link") & (F.action == "delete")))
async def link_confirm_delete_callback(
    callback: CallbackQuery,
    callback_data: ConfirmCallback,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    await LinkRepository(session).delete(callback_data.item_id, db_user.id)
    await edit_or_answer(callback, text(data, "links.deleted"))


@router.callback_query(LinkCallback.filter(F.action == "favorite"))
async def link_favorite_callback(
    callback: CallbackQuery,
    callback_data: LinkCallback,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    repository = LinkRepository(session)
    link = await repository.get(callback_data.link_id, db_user.id)
    if link is None:
        await callback.answer()
        return
    link = await repository.update_fields(link.id, db_user.id, is_favorite=not link.is_favorite)
    if link is None:
        await callback.answer()
        return
    await edit_or_answer(
        callback,
        text(data, "links.favorite_updated"),
        reply_markup=link_card_keyboard(link, catalog_from_data(data), language_from_data(data)),
    )


@router.callback_query(LinkCallback.filter(F.action == "refresh"))
async def link_refresh_callback(
    callback: CallbackQuery,
    callback_data: LinkCallback,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    try:
        link = await _link_service(session, data).refresh_metadata(
            user_id=db_user.id,
            link_id=callback_data.link_id,
        )
    except (MetadataFetchError, UrlValidationError):
        await edit_or_answer(callback, text(data, "validation.generic"))
        return
    if link is None:
        await callback.answer()
        return
    await edit_or_answer(
        callback,
        text(data, "links.refreshed"),
        reply_markup=link_card_keyboard(link, catalog_from_data(data), language_from_data(data)),
    )


@router.message(Command("export"))
async def export_command(
    message: Message,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    categories = await CategoryRepository(session).list_by_recent_use(db_user.id)
    await message.answer(
        text(data, "export.choose_scope"),
        reply_markup=export_scope_keyboard(
            categories, catalog_from_data(data), language_from_data(data)
        ),
    )


@router.callback_query(MenuCallback.filter(F.action == "export"))
async def export_menu_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    categories = await CategoryRepository(session).list_by_recent_use(db_user.id)
    await edit_or_answer(
        callback,
        text(data, "export.choose_scope"),
        reply_markup=export_scope_keyboard(
            categories, catalog_from_data(data), language_from_data(data)
        ),
    )


@router.callback_query(ExportScopeCallback.filter())
async def export_scope_callback(
    callback: CallbackQuery,
    callback_data: ExportScopeCallback,
    **data: Any,
) -> None:
    await edit_or_answer(
        callback,
        text(data, "export.choose_format"),
        reply_markup=export_format_keyboard(
            catalog_from_data(data),
            language_from_data(data),
            mode=callback_data.mode,
            category_id=callback_data.category_id,
        ),
    )


@router.callback_query(ExportCallback.filter())
async def export_callback(
    callback: CallbackQuery,
    callback_data: ExportCallback,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    features = data.get("features", {})
    if isinstance(features, dict) and not features.get("enable_export", True):
        await edit_or_answer(callback, text(data, "export.disabled"))
        return
    scope = ExportScope(
        mode=callback_data.mode,  # type: ignore[arg-type]
        category_id=callback_data.category_id or None,
    )
    service = ExportService(session)

    if callback_data.file_format == "message":
        title = await _scope_title(session, db_user.id, scope, data)
        body = await service.export_message(
            db_user.id,
            scope,
            title=title,
            empty_text=text(data, "export.message_empty"),
            truncated_template=text(data, "export.message_truncated", remaining="{remaining}"),
        )
        if callback.message is not None:
            await callback.message.answer(
                body,
                parse_mode="HTML",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        await callback.answer()
        return

    suffix = _export_filename_suffix(scope)
    if callback_data.file_format == "csv":
        payload = await service.export_csv(db_user.id, scope)
        filename = f"linkdooni-export-{suffix}.csv"
    else:
        payload = await service.export_json(db_user.id, scope)
        filename = f"linkdooni-export-{suffix}.json"
    if callback.message is not None:
        await callback.message.answer_document(
            BufferedInputFile(payload, filename=filename),
            caption=text(data, "export.ready"),
        )
    await callback.answer()


async def _scope_title(
    session: AsyncSession,
    user_id: int,
    scope: ExportScope,
    data: dict[str, Any],
) -> str:
    if scope.mode == "favorites":
        return text(data, "export.title_favorites")
    if scope.mode == "uncategorized":
        return text(data, "export.title_uncategorized")
    if scope.mode == "category" and scope.category_id:
        category = await CategoryRepository(session).get(scope.category_id, user_id)
        name = category.name if category else str(scope.category_id)
        return text(data, "export.title_category", name=name)
    return text(data, "export.title_all")


def _export_filename_suffix(scope: ExportScope) -> str:
    if scope.mode == "favorites":
        return "favorites"
    if scope.mode == "uncategorized":
        return "uncategorized"
    if scope.mode == "category" and scope.category_id:
        return f"category-{scope.category_id}"
    return "all"


async def collect_urls(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    data: dict[str, Any],
) -> None:
    urls = URLValidator().extract_urls(_message_text(message))
    if not urls:
        await message.answer(text(data, "links.add_prompt"))
        return
    await ask_for_category(message, state, session, db_user, data, urls)


async def ask_for_category(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    data: dict[str, Any],
    urls: list[str],
) -> None:
    await state.set_state(LinkStates.waiting_urls)
    await state.update_data(pending_urls=urls)
    categories = await CategoryRepository(session).list_by_recent_use(db_user.id)
    await message.answer(
        text(data, "links.choose_category", count=len(urls)),
        reply_markup=category_picker_keyboard(
            categories,
            catalog_from_data(data),
            language_from_data(data),
            purpose="save",
        ),
    )


async def perform_search(
    message: Message,
    query: str,
    session: AsyncSession,
    db_user: User,
    data: dict[str, Any],
) -> None:
    links = await SearchService(session).search(db_user.id, query)
    if not links:
        await message.answer(text(data, "search.empty"))
        return
    await message.answer(
        text(data, "search.results", query=query),
        reply_markup=links_list_keyboard(links, catalog_from_data(data), language_from_data(data)),
    )


async def send_favorites(
    message: Message,
    session: AsyncSession,
    db_user: User,
    data: dict[str, Any],
) -> None:
    links = await LinkRepository(session).list_favorites(db_user.id)
    body = text(data, "menu.favorites") if links else text(data, "search.empty")
    await message.answer(
        body,
        reply_markup=links_list_keyboard(links, catalog_from_data(data), language_from_data(data)),
    )




def _link_service(session: AsyncSession, data: dict[str, Any]) -> LinkService:
    settings = data.get("settings")
    validator = URLValidator()
    if isinstance(settings, Settings):
        fetcher = MetadataFetcher(
            validator=validator,
            timeout_seconds=settings.metadata_timeout_seconds,
            max_response_bytes=settings.metadata_max_response_bytes,
            max_redirects=settings.metadata_max_redirects,
        )
    else:
        fetcher = MetadataFetcher(validator=validator)
    return LinkService(session, validator=validator, metadata_fetcher=fetcher)


def _save_summary(result: SaveLinksResult, data: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.saved:
        lines.append(text(data, "links.saved", count=len(result.saved)))
    for duplicate in result.duplicates[:5]:
        lines.append(text(data, "links.duplicate", url=duplicate))
    if len(result.duplicates) > 5:
        lines.append(text(data, "links.duplicate_summary", count=len(result.duplicates)))
    for invalid in result.invalid[:5]:
        lines.append(text(data, "links.invalid_url", url=invalid))
    if result.metadata_failed:
        lines.append(text(data, "links.metadata_failed"))
    return "\n".join(lines) or text(data, "validation.generic")


def _message_text(message: Message) -> str:
    return message.text or message.caption or ""
