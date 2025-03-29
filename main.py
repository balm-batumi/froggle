# main.py
# Основной файл для запуска бота Froggle
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from loguru import logger
from config import BOT_TOKEN
from database import init_db
from handlers.ads_handler import ads_router
from handlers.menu_handler import menu_router
from handlers.ad_handler import ad_router
from handlers.admin_handler import admin_router
from states import AdsViewForm
from data.constants import get_main_menu_keyboard
from aiogram.fsm.context import FSMContext

logger.add("logs/froggle.log", rotation="10MB", compression="zip", level="DEBUG")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher(storage=MemoryStorage())

# Middleware для логирования callback-запросов
async def log_callback_middleware(handler, event: types.CallbackQuery, data: dict):
    logger.debug(f"Получен callback: data={event.data}, from_id={event.from_user.id}, current_state={await data['state'].get_state()}")
    return await handler(event, data)

dp.callback_query.outer_middleware(log_callback_middleware)

# Обработчик команды /start
@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    telegram_id = str(message.from_user.id)
    # Отправляем главное меню и сохраняем message_id
    menu_message = await message.answer(
        "🏠Главное меню\nУведомления: Нет",
        reply_markup=get_main_menu_keyboard()
    )
    await state.update_data(initial_message_id=menu_message.message_id)
    await state.set_state(AdsViewForm.select_category)
    logger.info(f"Главное меню отправлено для telegram_id={telegram_id}, message_id={menu_message.message_id}")

async def main():
    logger.info("Запуск бота Froggle...")
    await init_db()
    dp.include_router(ads_router)
    logger.debug("Подключен ads_router")
    dp.include_router(menu_router)
    logger.debug("Подключен menu_router")
    dp.include_router(ad_router)
    logger.debug("Подключен ad_router")
    dp.include_router(admin_router)
    logger.debug("Подключен admin_router")
    logger.info("Бот успешно настроен, начинаем polling...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())