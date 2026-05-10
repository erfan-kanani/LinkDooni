from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.helpers import catalog_from_data, edit_or_answer, language_from_data, text
from app.bot.keyboards.builders import main_menu, settings_keyboard
from app.bot.keyboards.callbacks import LanguageCallback, MenuCallback
from app.db.models import User
from app.db.repositories.users import UserRepository

router = Router(name="common")


@router.message(Command("start"))
async def start_command(message: Message, db_user: User, state: FSMContext, **data: Any) -> None:
    await state.clear()
    catalog = catalog_from_data(data)
    language = language_from_data(data)
    await message.answer(
        text(
            data,
            "welcome",
            first_name=db_user.first_name or db_user.username or "",
        ),
        reply_markup=main_menu(catalog, language),
    )


@router.message(Command("help"))
async def help_command(message: Message, **data: Any) -> None:
    catalog = catalog_from_data(data)
    language = language_from_data(data)
    await message.answer(text(data, "help"), reply_markup=main_menu(catalog, language))


@router.message(Command("settings"))
async def settings_command(message: Message, **data: Any) -> None:
    await message.answer(
        text(data, "settings.title"),
        reply_markup=settings_keyboard(catalog_from_data(data), language_from_data(data)),
    )


@router.callback_query(MenuCallback.filter(F.action == "home"))
async def home_callback(callback: CallbackQuery, state: FSMContext, **data: Any) -> None:
    await state.clear()
    catalog = catalog_from_data(data)
    language = language_from_data(data)
    await edit_or_answer(
        callback,
        text(data, "welcome", first_name=""),
        reply_markup=main_menu(catalog, language),
    )


@router.callback_query(MenuCallback.filter(F.action == "settings"))
async def settings_callback(callback: CallbackQuery, **data: Any) -> None:
    await edit_or_answer(
        callback,
        text(data, "settings.title"),
        reply_markup=settings_keyboard(catalog_from_data(data), language_from_data(data)),
    )


@router.callback_query(LanguageCallback.filter())
async def language_callback(
    callback: CallbackQuery,
    callback_data: LanguageCallback,
    session: AsyncSession,
    db_user: User,
    **data: Any,
) -> None:
    await UserRepository(session).set_language(db_user.id, callback_data.code)
    db_user.language_code = callback_data.code
    await edit_or_answer(
        callback,
        text(data, "settings.language_updated"),
        reply_markup=settings_keyboard(catalog_from_data(data), language_from_data(data)),
    )
