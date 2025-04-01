# main.py
# Основной файл для запуска бота Froggle
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from loguru import logger
from config import BOT_TOKEN
from database import init_db, get_db, Subscription, Advertisement, ViewedAds, User, select
from handlers.ads_handler import ads_router
from handlers.menu_handler import menu_router
from handlers.ad_handler import ad_router
from handlers.admin_handler import admin_router
from states import AdsViewForm
from data.constants import get_main_menu_keyboard
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey  # Исправленный импорт

logger.add("logs/froggle.log", rotation="10MB", compression="zip", level="DEBUG")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher(storage=MemoryStorage())

# Middleware для логирования callback-запросов
async def log_callback_middleware(handler, event: types.CallbackQuery, data: dict):
    logger.debug(f"Получен callback: data={event.data}, from_id={event.from_user.id}, current_state={await data['state'].get_state()}")
    return await handler(event, data)


# Middleware для удаления уведомлений при действиях пользователя
async def clean_notification(handler, event, data):
    telegram_id = event.from_user.id
    state = FSMContext(storage=dp.storage, key=StorageKey(bot_id=bot.id, chat_id=telegram_id, user_id=telegram_id))
    data_state = await state.get_data()

    # Удаление уведомления о подписке (существующая логика)
    notification_id = data_state.get("notification_id")
    if notification_id:
        try:
            await bot.delete_message(chat_id=telegram_id, message_id=notification_id)
            await state.update_data(notification_id=None)
            logger.debug(f"Уведомление message_id={notification_id} удалено для telegram_id={telegram_id}")
        except Exception as e:
            logger.error(f"Ошибка удаления уведомления message_id={notification_id}: {e}")

    # Удаление уведомления об отклонении объявления
    rejection_notification_id = data_state.get("rejection_notification_id")
    if rejection_notification_id:
        try:
            await bot.delete_message(chat_id=telegram_id, message_id=rejection_notification_id)
            await state.update_data(rejection_notification_id=None)
            logger.debug(
                f"Уведомление об отклонении message_id={rejection_notification_id} удалено для telegram_id={telegram_id}")
        except Exception as e:
            logger.error(f"Ошибка удаления уведомления об отклонении message_id={rejection_notification_id}: {e}")

    return await handler(event, data)

# Регистрация middleware после определения dp
dp.callback_query.outer_middleware(log_callback_middleware)
dp.callback_query.middleware(clean_notification)
dp.message.middleware(clean_notification)

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
    # asyncio.create_task(notify_subscribers())  # Закомментирован нотификатор
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())