from aiogram.filters.callback_data import CallbackData


class MenuCallback(CallbackData, prefix="m"):
    action: str


class CategoryCallback(CallbackData, prefix="c"):
    action: str
    category_id: int = 0


class LinkCallback(CallbackData, prefix="l"):
    action: str
    link_id: int


class PickCategoryCallback(CallbackData, prefix="pc"):
    purpose: str
    category_id: int
    link_id: int = 0


class ConfirmCallback(CallbackData, prefix="x"):
    entity: str
    action: str
    item_id: int


class EditLinkCallback(CallbackData, prefix="e"):
    link_id: int
    field: str


class LanguageCallback(CallbackData, prefix="lang"):
    code: str


class ExportScopeCallback(CallbackData, prefix="exs"):
    mode: str
    category_id: int = 0


class ExportCallback(CallbackData, prefix="ex"):
    file_format: str
    mode: str = "all"
    category_id: int = 0
