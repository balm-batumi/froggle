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
    menu_message = await message.answer(
        "🏠Главное меню\nУведомления: Нет",
        reply_markup=get_main_menu_keyboard()
    )
    await state.update_data(initial_message_id=menu_message.message_id)
    await state.set_state(AdsViewForm.select_category)
    logger.info(f"Главное меню отправлено для telegram_id={telegram_id}, message_id={menu_message.message_id}")

# Асинхронная функция для уведомления подписчиков (закомментирована)
# async def notify_subscribers():
#     while True:
#         logger.info("Проверка подписок для уведомлений...")
#         async for session in get_db():
#             subscriptions = await session.execute(select(Subscription))
#             subscriptions = subscriptions.scalars().all()
#             for sub in subscriptions:
#                 user_result = await session.execute(select(User.is_admin).where(User.id == sub.user_id))
#                 is_admin = user_result.scalar_one_or_none() or False
#                 query = (
#                     select(Advertisement)
#                     .where(
#                         Advertisement.status == "approved",
#                         Advertisement.city == sub.city,
#                         Advertisement.category == sub.category,
#                         Advertisement.tags.any(sub.tags[0])
#                     )
#                 )
#                 if not is_admin:
#                     query = query.where(~Advertisement.id.in_(
#                         select(ViewedAds.advertisement_id)
#                         .join(User)
#                         .where(User.id == sub.user_id)
#                     ))
#                 result = await session.execute(query)
#                 pending_ads = result.scalars().all()
#                 missed_count = len(pending_ads)
#                 logger.debug(f"Для user_id={sub.user_id}: найдено {missed_count} объявлений, подписка: city={sub.city}, category={sub.category}, tags={sub.tags}")
#                 if missed_count > 0:
#                     keyboard = types.InlineKeyboardMarkup(inline_keyboard=[[
#                         types.InlineKeyboardButton(text="Смотреть", callback_data="view_subscription_ads")
#                     ]])
#                     text = f"У вас {missed_count} непросмотренных объявлений по вашей подписке"
#                     try:
#                         await bot.send_message(
#                             chat_id=sub.user_id,
#                             text=text,
#                             reply_markup=keyboard
#                         )
#                         logger.info(f"Отправлено уведомление для user_id={sub.user_id}, count={missed_count}")
#                     except Exception as e:
#                         logger.error(f"Ошибка отправки уведомления для user_id={sub.user_id}: {e}")
#         await asyncio.sleep(600)

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