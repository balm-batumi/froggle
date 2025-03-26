import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties  # Исправленный импорт
from config import BOT_TOKEN  # Предполагаю, что токен в config.py

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# Reply-клавиатура с кнопкой "Меню"
menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Меню")]],
    resize_keyboard=True,
    one_time_keyboard=False
)

# Аналог главного меню Froggle как inline-клавиатура
def get_inline_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Услуги", callback_data="category:services"),
         InlineKeyboardButton(text="Еда", callback_data="category:food"),
         InlineKeyboardButton(text="Жильё", callback_data="category:housing")],
        [InlineKeyboardButton(text="Общение", callback_data="category:communication"),
         InlineKeyboardButton(text="Авто", callback_data="category:auto"),
         InlineKeyboardButton(text="Барахолка", callback_data="category:market")],
        [InlineKeyboardButton(text="Шоппинг", callback_data="category:shopping")],
        [InlineKeyboardButton(text="Помощь", callback_data="action:help"),
         InlineKeyboardButton(text="Назад", callback_data="action:back")]
    ])

# Обработчик команды /start
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "Тест подписки: вы получите эмуляционные объявления.\nНажмите 'Меню' для главного меню.",
        reply_markup=menu_keyboard
    )
    # Запускаем эмуляцию рассылки
    asyncio.create_task(send_emulated_ads(message.chat.id))

# Обработчик нажатия кнопки "Меню"
@dp.message(lambda message: message.text == "Меню")
async def menu_handler(message: types.Message):
    await message.answer(
        "Добро пожаловать в тестовое меню Froggle! Выберите категорию:",
        reply_markup=get_inline_main_menu()
    )

# Эмуляция рассылки объявлений
async def send_emulated_ads(chat_id: int):
    ad_count = 1
    while True:
        await asyncio.sleep(5)  # Каждые 5 секунд
        ad_text = (
            f"•••••••     Объявление #{ad_count}:     •••••••\n"
            f"🏷️ тест, эмуляция\n"
            f"<b>Тестовое объявление {ad_count}</b>\n"
            f"Это тестовое объявление #{ad_count}\n"
            f"💰 {ad_count * 100}$\n"
            f"📞 @testuser"
        )
        await bot.send_message(chat_id=chat_id, text=ad_text)
        ad_count += 1

# Запуск бота
async def main():
    print("Тестовый бот запущен. Используйте /start для начала.")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())