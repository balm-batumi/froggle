from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from database import init_db
from handlers.menu_handler import menu_router
from handlers.ad_handler import ad_router
from handlers.admin_handler import admin_router
from handlers.ads_handler import ads_router
import asyncio
from loguru import logger

logger.add("logs/bot.log", rotation="10MB", compression="zip", level="INFO")

async def main():
    logger.info("Запуск бота Froggle...")
    await init_db()
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode='HTML')
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(ads_router)  # Сначала ads_router для категорий
    dp.include_router(menu_router)  # Потом menu_router для базовых команд
    dp.include_router(ad_router)
    dp.include_router(admin_router)
    logger.info("Бот успешно настроен, начинаем polling...")
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    asyncio.run(main())