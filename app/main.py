import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.bot.handlers import build_router
from app.bot.middlewares.database import DatabaseMiddleware
from app.config.settings import get_settings
from app.db.session import create_engine, create_session_factory, init_db
from app.utils.i18n import MessageCatalog, load_feature_flags
from app.utils.logging import configure_logging, get_logger


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)

    features = load_feature_flags(settings.config_dir / "features.yaml")
    default_language = str(features.get("default_language", "fa"))
    catalog = MessageCatalog(
        settings.config_dir / "messages.yaml", default_language=default_language
    )

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    if settings.auto_create_db:
        await init_db(engine)

    if settings.telegram_bot_token is None:
        msg = "TELEGRAM_BOT_TOKEN is required to run the bot."
        raise RuntimeError(msg)

    bot = Bot(
        token=settings.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher["settings"] = settings
    dispatcher["features"] = features

    database_middleware = DatabaseMiddleware(
        session_factory,
        catalog,
        default_language=default_language,
    )
    dispatcher.message.middleware(database_middleware)
    dispatcher.callback_query.middleware(database_middleware)
    dispatcher.inline_query.middleware(database_middleware)
    dispatcher.include_router(build_router())

    await set_commands(bot, catalog)
    logger.info("bot_starting")
    await dispatcher.start_polling(bot)


async def set_commands(bot: Bot, catalog: MessageCatalog) -> None:
    command_keys = [
        ("start", "commands.start"),
        ("help", "commands.help"),
        ("categories", "commands.categories"),
        ("add", "commands.add"),
        ("search", "commands.search"),
        ("favorites", "commands.favorites"),
        ("export", "commands.export"),
        ("settings", "commands.settings"),
    ]
    for language in catalog.languages:
        commands = [
            BotCommand(command=command, description=catalog.t(language, key))
            for command, key in command_keys
        ]
        await bot.set_my_commands(commands, language_code=language)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
