"""Bot handlers."""

from aiogram import Router

from app.bot.handlers import categories, common, inline, links


def build_router() -> Router:
    router = Router(name="linkdooni")
    router.include_router(common.router)
    router.include_router(categories.router)
    router.include_router(links.router)
    router.include_router(inline.router)
    return router
