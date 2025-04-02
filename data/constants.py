from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from data.categories import CATEGORIES

# Создает главное меню с категориями, "ℹ️" (Помощь) и "Настройки"
def get_main_menu_keyboard():
    buttons = [
        InlineKeyboardButton(text=CATEGORIES[cat]["display_name"], callback_data=f"category:{cat}")
        for cat in CATEGORIES
    ]
    buttons.extend([
        InlineKeyboardButton(text="ℹ️", callback_data="action:help"),
        InlineKeyboardButton(text="Настройки", callback_data="action:settings")
    ])
    keyboard_rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)