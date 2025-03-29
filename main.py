# Middleware для логирования всех входящих callback-запросов
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from database import init_db
from handlers.menu_handler import menu_router
from handlers.ad_handler import ad_router
from handlers.admin_handler import admin_router
from handlers.ads_handler import ads_router
from tools.middlewares import NetworkErrorMiddleware
import asyncio
from loguru import logger

logger.add("logs/bot.log", rotation="10MB", compression="zip", level="DEBUG")

# Middleware для перехвата и логирования callback-запросов
# Логирует текущее состояние для отладки маршрутизации
async def log_callback_middleware(handler, update, data):
    if update.callback_query:
        callback_data = update.callback_query.data
        from_id = update.callback_query.from_user.id
        state = data.get("state")  # Получаем FSMContext из data
        current_state = await state.get_state() if state else "None"
        logger.debug(f"Получен callback: data={callback_data}, from_id={from_id}, current_state={current_state}")
    return await handler(update, data)

# Основной файл запуска бота Froggle
# Логирует подключение роутеров для отладки маршрутизации
async def main():
    logger.info("Запуск бота Froggle...")
    await init_db()
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode='HTML')
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(ads_router)
    logger.debug("Подключен ads_router")
    dp.include_router(menu_router)
    logger.debug("Подключен menu_router")
    dp.include_router(ad_router)
    logger.debug("Подключен ad_router")
    dp.include_router(admin_router)
    logger.debug("Подключен admin_router")
    # dp.update.middleware(NetworkErrorMiddleware())
    dp.update.middleware(log_callback_middleware)  # Добавляем middleware для callback'ов
    logger.info("Бот успешно настроен, начинаем polling...")
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    asyncio.run(main())