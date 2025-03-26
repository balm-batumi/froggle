from aiogram.fsm.state import State, StatesGroup

class MenuState(StatesGroup):
    category = State()

class AdAddForm(StatesGroup):
    city = State()
    tags = State()
    title = State()
    description = State()
    price = State()  # Новая строка
    media = State()
    contacts = State()
    confirm = State()

class AdminForm(StatesGroup):
    moderation = State()  # Добавляем нужное состояние
    confirm_delete = State()

class AdsViewForm(StatesGroup):
    select_category = State()
    select_city = State()
    select_tags = State()

