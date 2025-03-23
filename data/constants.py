from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Временный хардкод категорий до создания data/categories.py
CATEGORIES = ["Услуги", "Еда", "Жильё", "Общение", "Авто", "Барахолка", "Шоппинг"]

# Главное меню с инлайн-кнопками
def get_main_menu_keyboard():
    buttons = [
        InlineKeyboardButton(text=category, callback_data=f"category:{category}")
        for category in CATEGORIES
    ]
    # Добавляем "Помощь" и "Настройки" в последнюю строку
    buttons.extend([
        InlineKeyboardButton(text="Помощь", callback_data="action:help"),
        InlineKeyboardButton(text="Настройки", callback_data="action:settings")
    ])
    keyboard_rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)