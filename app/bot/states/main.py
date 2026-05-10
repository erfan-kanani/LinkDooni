from aiogram.fsm.state import State, StatesGroup


class CategoryStates(StatesGroup):
    waiting_name = State()
    waiting_rename = State()


class LinkStates(StatesGroup):
    waiting_urls = State()
    waiting_save_category_name = State()
    waiting_search = State()
    waiting_edit_value = State()
