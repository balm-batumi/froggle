# tools/adsender.py
# Бот для имитации стороннего рекламодателя, отправляет тестовые объявления в Froggle через API
import asyncio
import random
import os
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command  # Импорт Command для aiogram 3.x
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from config import BOT_TOKEN_AD, DATABASE_URL  # Импорт токена и URL базы из config.py
from database import get_db, get_all_category_tags  # Импорт функций для работы с базой
import requests

# Настройка логирования
logger.add("logs/adsender.log", rotation="10MB", compression="zip", level="DEBUG")

# Инициализация бота
bot = Bot(token=BOT_TOKEN_AD, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher(storage=MemoryStorage())

# URL API Froggle (локальный адрес для тестов)
FROGGLE_API_URL = "http://localhost:8000/api/notify_admins"
API_KEY = "secret_key"  # Временный ключ для тестов

# Списки для генерации данных
CATEGORIES = ["services", "food", "housing", "communication", "auto", "market", "shopping"]
CITIES = ["Тбилиси", "Батуми", "Кутаиси"]
DESCRIPTIONS = [
    "Отличное предложение от AdSenderBot!",
    "Срочно! Тестовое объявление!",
    "Супер акция, проверьте сейчас!",
    "Только для тестов, не пропустите!",
    "Не упусти шанс! Уникальное предложение!",
    "Новинка! Проверь прямо сейчас!",
    "🔥 Горячее объявление, успей первым!",
    "Ваш идеальный вариант уже здесь!",
    "🚀 Тестовая публикация, не пропусти!",
    "📢 Внимание! Эксклюзивная акция!",
    "Скидки только сегодня, заходи!",
    "Лучшее предложение на рынке!",
    "Пробное объявление, оцени сам!",
    "Успей воспользоваться выгодой сейчас!"
]
PRICES = ["100$", "250$", "500$", None]
MEDIA_FOLDER = "C:/Users/user/PycharmProjects/Froggle/test_media"  # Путь к папке с тестовыми фото

# Команда /start
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    logger.info(f"Получена команда /start от telegram_id={message.from_user.id}")
    await message.answer("Это AdSenderBot. Используйте /send_ad для отправки тестового объявления в Froggle.")

# Команда /send_ad
@dp.message(Command("send_ad"))
async def send_ad_handler(message: types.Message):
    logger.info(f"Получена команда /send_ad от telegram_id={message.from_user.id}")

    # Генерация тестового объявления
    category = random.choice(CATEGORIES)
    city = random.choice(CITIES)
    async for session in get_db():
        tags_list = await get_all_category_tags(category)  # Получаем теги для категории
        if not tags_list:
            await message.answer(f"Ошибка: Нет тегов для категории '{category}' в базе.")
            return
        tag = random.choice(tags_list)[1]  # Берём name из кортежа (id, name)

    title_ru = f"Тестовое объявление #{random.randint(1000, 9999)}"
    description_ru = random.choice(DESCRIPTIONS)
    price = random.choice(PRICES)

    media_files = [f for f in os.listdir(MEDIA_FOLDER) if f.endswith(('.jpg', '.png', '.jpeg'))]
    if not media_files:
        await message.answer("Ошибка: Нет тестовых фото в папке test_media.")
        return
    random_media = random.choice(media_files)
    media_path = os.path.join(MEDIA_FOLDER, random_media)

    # Формируем данные для API Froggle
    data = {
        "category": category,
        "city": city,
        "tags": tag,
        "title_ru": title_ru,
        "description_ru": description_ru,
        "price": price if price else "",
        "contact_info": "@TestSender",
        "status": "pending",
        "is_test": True,
        "api_key": API_KEY,
        "user_id": "7937566977"
    }

    # Отправляем данные и файл через API
    try:
        with open(media_path, "rb") as media_file:
            files = {"media": (random_media, media_file, "image/jpeg")}
            response = requests.post(
                FROGGLE_API_URL,
                data=data,
                files=files
            )
        if response.status_code == 200:
            ad_id = response.json().get("ad_id")  # Предполагаем, что Froggle вернёт ID
            logger.info(f"Успешно отправлено тестовое объявление #{ad_id} в Froggle")
            await message.answer(f"Тестовое объявление #{ad_id} отправлено в Froggle на модерацию.")
        else:
            logger.error(f"Ошибка API Froggle: {response.status_code} - {response.text}")
            await message.answer(f"Ошибка при отправке в Froggle: {response.status_code}")
    except Exception as e:
        logger.error(f"Ошибка при отправке в API: {e}")
        await message.answer(f"Ошибка при отправке в Froggle: {str(e)}")

async def main():
    logger.info("Запуск AdSenderBot...")
    logger.debug("Polling started")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())