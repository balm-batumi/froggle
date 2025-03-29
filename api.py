# api.py
# API-сервер для Froggle, принимает тестовые объявления от AdSenderBot
import asyncio
import random
import os
from fastapi import FastAPI, UploadFile, Form, HTTPException
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.types import FSInputFile  # Для работы с локальными файлами
from aiogram.exceptions import TelegramAPIError  # Для обработки ошибок Telegram
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from config import BOT_TOKEN, DATABASE_URL  # Импорт токена и URL базы из config.py
from database import Advertisement, User, get_db, get_all_category_tags
from sqlalchemy import select
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey  # Для работы с FSMContext
from data.constants import get_main_menu_keyboard  # Для клавиатуры
import json

# Настройка логирования
logger.add("logs/api.log", rotation="10MB", compression="zip", level="DEBUG")

# Инициализация FastAPI и бота Froggle
app = FastAPI()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
storage = MemoryStorage()  # Для работы с FSMContext в API

# ID канала для загрузки фото и админа для уведомлений
CHAT_ID_HOUSING = -1002575896997
ADMIN_CHAT_ID = 8162326543

# Эндпоинт для получения объявлений от AdSenderBot
@app.post("/api/notify_admins")
async def notify_admins(
    category: str = Form(...),
    city: str = Form(...),
    tags: str = Form(...),
    title_ru: str = Form(...),
    description_ru: str = Form(...),
    price: str = Form(default=""),
    contact_info: str = Form(...),
    status: str = Form(...),
    is_test: bool = Form(...),
    user_id: str = Form(...),  # telegram_id пользователя
    api_key: str = Form(...),
    media: UploadFile = Form(...)
):
    logger.info(f"Получен запрос на /api/notify_admins с api_key={api_key}")

    # Проверка API-ключа
    if api_key != "secret_key":  # Временный ключ, позже заменим на безопасный
        logger.error(f"Неверный api_key: {api_key}")
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Получаем user_id из базы по telegram_id
    async for session in get_db():
        result = await session.execute(select(User.id).where(User.telegram_id == user_id))
        db_user_id = result.scalar_one_or_none()
        if not db_user_id:
            logger.error(f"Пользователь с telegram_id={user_id} не найден")
            raise HTTPException(status_code=400, detail="User not found")

        # Получаем теги для категории
        tags_list = await get_all_category_tags(category)
        if not tags_list:
            logger.error(f"Нет тегов для категории '{category}'")
            raise HTTPException(status_code=400, detail=f"No tags for category '{category}'")
        valid_tags = [tag[1] for tag in tags_list]  # Список имён тегов
        tag = tags if tags in valid_tags else random.choice(tags_list)[1]  # Проверяем тег или берём случайный

        # Загружаем фото через токен Froggle в канал
        try:
            # Сохраняем файл временно
            file_content = await media.read()
            temp_file_path = f"temp_{media.filename}"
            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(file_content)

            # Отправляем фото в канал CHAT_ID_HOUSING
            photo = FSInputFile(temp_file_path)
            sent_photo = await bot.send_photo(chat_id=CHAT_ID_HOUSING, photo=photo)
            media_file_id = sent_photo.photo[-1].file_id

            # Удаляем временный файл
            os.remove(temp_file_path)

            # Создаём объявление
            ad = Advertisement(
                user_id=db_user_id,
                category=category,
                city=city,
                tags=[tag],
                title_ru=title_ru,
                description_ru=description_ru,
                price=price if price else None,
                media_file_ids=[{"id": media_file_id, "type": "photo"}],
                contact_info=contact_info,
                status=status,
                is_test=is_test
            )
            session.add(ad)
            await session.commit()
            await session.refresh(ad)
            ad_id = ad.id
            logger.info(f"Добавлено тестовое объявление #{ad_id} в advertisements")

            # Редактируем сообщение с меню и уведомлением для админа
            state = FSMContext(
                storage=storage,
                key=StorageKey(bot_id=bot.id, chat_id=ADMIN_CHAT_ID, user_id=ADMIN_CHAT_ID)
            )
            logger.debug(f"Создан FSMContext для chat_id={ADMIN_CHAT_ID}, user_id={ADMIN_CHAT_ID}")
            data = await state.get_data()
            initial_message_id = data.get("initial_message_id")
            logger.debug(f"Получен initial_message_id из состояния: {initial_message_id}")
            full_text = f"🏠Главное меню\nУведомления: Новое объявление #{ad_id} добавлено на модерацию"
            if initial_message_id:
                logger.debug(f"Попытка редактирования сообщения #{initial_message_id} с текстом: {full_text}")
                try:
                    await bot.edit_message_text(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=initial_message_id,
                        text=full_text,
                        reply_markup=get_main_menu_keyboard()
                    )
                    logger.info(f"Успешно отредактировано сообщение #{initial_message_id} для ad_id={ad_id}")
                except TelegramAPIError as e:
                    logger.error(f"Ошибка редактирования сообщения #{initial_message_id}: {e}")
                    # Если редактирование не удалось, отправляем новое сообщение
                    menu_message = await bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=full_text,
                        reply_markup=get_main_menu_keyboard()
                    )
                    logger.info(f"Отправлено новое сообщение с message_id={menu_message.message_id} для ad_id={ad_id}")
                    await state.update_data(initial_message_id=menu_message.message_id)
                    logger.debug(f"Обновлён initial_message_id в состоянии: {menu_message.message_id}")
            else:
                # Если сообщение не найдено (например, первый запуск), отправляем новое
                logger.debug(f"initial_message_id отсутствует, отправляем новое сообщение для ad_id={ad_id}")
                menu_message = await bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=full_text,
                    reply_markup=get_main_menu_keyboard()
                )
                logger.info(f"Отправлено первое сообщение с message_id={menu_message.message_id} для ad_id={ad_id}")
                await state.update_data(initial_message_id=menu_message.message_id)
                logger.debug(f"Сохранён initial_message_id в состоянии: {menu_message.message_id}")

            # Возвращаем только ad_id как простой словарь
            return {"ad_id": ad_id}
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса: {e}")
            raise HTTPException(status_code=500, detail=str(e))

async def main():
    logger.info("Запуск API Froggle...")
    # FastAPI запускается через uvicorn в терминале

if __name__ == "__main__":
    asyncio.run(main())