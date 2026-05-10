from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.helpers import catalog_from_data, edit_or_answer, language_from_data, text
from app.bot.keyboards.builders import main_menu
from app.bot.keyboards.callbacks import MenuCallback
from app.db.models import User

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
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def help_command(message: Message, **data: Any) -> None:
    catalog = catalog_from_data(data)
    language = language_from_data(data)
    await message.answer(
        text(data, "help"),
        reply_markup=main_menu(catalog, language),
        parse_mode="HTML",
    )


@router.callback_query(MenuCallback.filter(F.action == "home"))
async def home_callback(
    callback: CallbackQuery, state: FSMContext, db_user: User, **data: Any
) -> None:
    await state.clear()
    catalog = catalog_from_data(data)
    language = language_from_data(data)
    first_name = db_user.first_name or db_user.username or ""
    await edit_or_answer(
        callback,
        text(data, "welcome", first_name=first_name),
        reply_markup=main_menu(catalog, language),
        parse_mode="HTML",
    )
