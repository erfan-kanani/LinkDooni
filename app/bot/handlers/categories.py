from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.helpers import catalog_from_data, edit_or_answer, language_from_data, text
from app.bot.keyboards.builders import (
    categories_keyboard,
    category_actions_keyboard,
    confirm_keyboard,
)
from app.bot.keyboards.callbacks import CategoryCallback, ConfirmCallback, MenuCallback
from app.bot.states.main import CategoryStates
from app.db.models import User
from app.db.repositories.categories import CategoryRepository
from app.db.repositories.links import LinkRepository

router = Router(name="categories")


@router.message(Command("categories"))
async def categories_command(
    message: Message, session: AsyncSession, db_user: User, **data: Any
) -> None:
    await send_categories(message, session, db_user, data)


@router.callback_query(MenuCallback.filter(F.action == "categories"))
async def categories_menu_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    categories = await CategoryRepository(session).list_for_user(db_user.id)
    await edit_or_answer(
        callback,
        _categories_text(data, bool(categories)),
        reply_markup=categories_keyboard(
            categories, catalog_from_data(data), language_from_data(data)
        ),
    )


@router.callback_query(CategoryCallback.filter(F.action == "create"))
async def category_create_callback(callback: CallbackQuery, state: FSMContext, **data: Any) -> None:
    await state.set_state(CategoryStates.waiting_name)
    await edit_or_answer(callback, text(data, "categories.create_prompt"))


@router.message(CategoryStates.waiting_name)
async def category_create_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer(text(data, "categories.create_prompt"))
        return
    category = await CategoryRepository(session).create(db_user.id, name)
    await state.clear()
    await message.answer(text(data, "categories.created", name=category.name))
    await send_categories(message, session, db_user, data)


@router.callback_query(CategoryCallback.filter(F.action == "rename"))
async def category_rename_callback(
    callback: CallbackQuery,
    callback_data: CategoryCallback,
    state: FSMContext,
    **data: Any,
) -> None:
    await state.set_state(CategoryStates.waiting_rename)
    await state.update_data(category_id=callback_data.category_id)
    await edit_or_answer(callback, text(data, "categories.rename_prompt"))


@router.message(CategoryStates.waiting_rename)
async def category_rename_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    name = (message.text or "").strip()
    state_data = await state.get_data()
    category_id = int(state_data.get("category_id", 0))
    if not name or not category_id:
        await message.answer(text(data, "categories.rename_prompt"))
        return
    category = await CategoryRepository(session).rename(category_id, db_user.id, name)
    await state.clear()
    await message.answer(text(data, "categories.renamed", name=category.name if category else name))
    await send_categories(message, session, db_user, data)


@router.callback_query(CategoryCallback.filter(F.action == "delete"))
async def category_delete_callback(
    callback: CallbackQuery,
    callback_data: CategoryCallback,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    category = await CategoryRepository(session).get(callback_data.category_id, db_user.id)
    if category is None:
        await callback.answer()
        return
    await edit_or_answer(
        callback,
        text(data, "categories.delete_confirm", name=category.name),
        reply_markup=confirm_keyboard(
            "category",
            category.id,
            catalog_from_data(data),
            language_from_data(data),
        ),
    )


@router.callback_query(ConfirmCallback.filter((F.entity == "category") & (F.action == "delete")))
async def category_confirm_delete_callback(
    callback: CallbackQuery,
    callback_data: ConfirmCallback,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    await CategoryRepository(session).delete(callback_data.item_id, db_user.id)
    categories = await CategoryRepository(session).list_for_user(db_user.id)
    await edit_or_answer(
        callback,
        text(data, "categories.deleted"),
        reply_markup=categories_keyboard(
            categories, catalog_from_data(data), language_from_data(data)
        ),
    )


@router.callback_query(CategoryCallback.filter(F.action == "open"))
async def category_open_callback(
    callback: CallbackQuery,
    callback_data: CategoryCallback,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    repository = CategoryRepository(session)
    category_id = callback_data.category_id or None
    category = await repository.get(category_id, db_user.id) if category_id else None
    links = await LinkRepository(session).list_by_category(db_user.id, category_id, limit=1)
    title = category.name if category else text(data, "categories.uncategorized")
    if not links:
        body = f"{title}\n\n{text(data, 'links.empty_category')}"
    else:
        body = f"{title}\n\n{text(data, 'links.category_cards_intro')}"
    await edit_or_answer(
        callback,
        body,
        reply_markup=category_actions_keyboard(
            category,
            links,
            catalog_from_data(data),
            language_from_data(data),
        ),
    )


async def send_categories(
    message: Message,
    session: AsyncSession,
    db_user: User,
    data: dict[str, Any],
) -> None:
    categories = await CategoryRepository(session).list_for_user(db_user.id)
    await message.answer(
        _categories_text(data, bool(categories)),
        reply_markup=categories_keyboard(
            categories, catalog_from_data(data), language_from_data(data)
        ),
    )


def _categories_text(data: dict[str, Any], has_categories: bool) -> str:
    if has_categories:
        return f"{text(data, 'categories.title')}\n\n{text(data, 'categories.browse_hint')}"
    return text(data, "categories.empty")
