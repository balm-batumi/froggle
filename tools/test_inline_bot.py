from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties  # Добавлен импорт
import asyncio
from config import BOT_TOKEN  # Импорт токена из config.py

# Создание бота с использованием DefaultBotProperties
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Хардкод данных
CATEGORIES = ["Услуги", "Еда", "Жильё"]
CITIES = {
    "Услуги": [("Тбилиси", 5), ("Батуми", 3), ("Кутаиси", 2)],
    "Еда": [("Тбилиси", 4), ("Батуми", 2), ("Гори", 1)],
    "Жильё": [("Тбилиси", 3), ("Кутаиси", 2), ("Батуми", 1)]
}
ADS = {
    "Услуги": {
        "Тбилиси": ["Объявление 1: Уборка", "Объявление 2: Ремонт", "Объявление 3: Консультация"],
        "Батуми": ["Объявление 1: Парикмахер", "Объявление 2: Массаж"],
        "Кутаиси": ["Объявление 1: Ремонт техники"]
    },
    "Еда": {
        "Тбилиси": ["Объявление 1: Хачапури", "Объявление 2: Хинкали"],
        "Батуми": ["Объявление 1: Кофе"],
        "Гори": ["Объявление 1: Шашлык"]
    },
    "Жильё": {
        "Тбилиси": ["Объявление 1: Квартира 1к", "Объявление 2: Дом"],
        "Кутаиси": ["Объявление 1: Комната"],
        "Батуми": ["Объявление 1: Апартаменты"]
    }
}

# Главное меню
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Услуги", callback_data="category:Услуги"),
         InlineKeyboardButton(text="Еда", callback_data="category:Еда"),
         InlineKeyboardButton(text="Жильё", callback_data="category:Жильё")]
    ])
    await message.answer("Выберите категорию:", reply_markup=keyboard)

# Обработка выбора категории
@dp.callback_query(lambda call: call.data.startswith("category:"))
async def show_cities(call: types.CallbackQuery):
    category = call.data.split(":")[1]
    cities = CITIES.get(category, [])

    if not cities:
        await call.message.edit_text(f"Нет городов для категории '{category}'.")
        return

    buttons = [
        InlineKeyboardButton(text=f"{city} ({count})", callback_data=f"city:{category}:{city}")
        for city, count in cities
    ]
    keyboard_rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await call.message.edit_text(
        f"Выберите город для категории '{category}':",
        reply_markup=keyboard
    )
    await call.answer()

# Обработка выбора города и вывод объявлений
@dp.callback_query(lambda call: call.data.startswith("city:"))
async def show_ads(call: types.CallbackQuery):
    _, category, city = call.data.split(":")
    ads = ADS.get(category, {}).get(city, [])

    if not ads:
        await call.message.edit_text(f"Нет объявлений для '{city}' в категории '{category}'.")
        return

    # Удаляем сообщение с городами
    await call.message.delete()

    # Заглушка
    await call.message.bot.send_message(
        chat_id=call.from_user.id,
        text="Временно фильтрация по тегам отключена"
    )

    # Вывод объявлений в отдельных сообщениях
    for ad in ads:
        await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text=ad
        )

    # Кнопки действий
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Помощь", callback_data="action:help"),
         InlineKeyboardButton(text="Добавить своё", callback_data="action:add"),
         InlineKeyboardButton(text="Назад", callback_data="action:back")]
    ])
    await call.message.bot.send_message(
        chat_id=call.from_user.id,
        text="Выберите действие:",
        reply_markup=keyboard
    )
    await call.answer()

# Обработка действий
@dp.callback_query(lambda call: call.data.startswith("action:"))
async def handle_action(call: types.CallbackQuery):
    action = call.data.split(":")[1]

    if action == "help":
        await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text="Это помощь. Выберите категорию снова с /start."
        )
    elif action == "add":
        await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text="Добавление пока не реализовано в тесте."
        )
    elif action == "back":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Услуги", callback_data="category:Услуги"),
             InlineKeyboardButton(text="Еда", callback_data="category:Еда"),
             InlineKeyboardButton(text="Жильё", callback_data="category:Жильё")]
        ])
        await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text="Выберите категорию:",
            reply_markup=keyboard
        )

    await call.answer()

# Запуск бота
async def main():
    print("Тестовый бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())