# tools/adsender_service_tbilisi.py
# Бот для имитации рекламодателя, отправляет тестовые объявления в Froggle (Тбилиси, Услуги, Ремонт и стройка)
import asyncio
import random
import os
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from loguru import logger
from config import BOT_TOKEN_AD
from database import get_db  # Оставил, если понадобится база
import requests

# Настройка логирования
logger.add("logs/adsender_service_tbilisi.log", rotation="10MB", compression="zip", level="DEBUG")

# Инициализация бота
bot = Bot(token=BOT_TOKEN_AD, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher(storage=MemoryStorage())

# URL API Froggle (локальный адрес для тестов)
FROGGLE_API_URL = "http://localhost:8000/api/notify_admins"
API_KEY = "secret_key"  # Временный ключ для тестов

# Фиксированные данные
CITY = "Тбилиси"
CATEGORY = "services"
TAG = "Ремонт и стройка"  # Один фиксированный тег
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
    await message.answer("Это AdSenderServiceTbilisi. Используйте /send_ad для отправки тестового объявления в Froggle (Тбилиси, Услуги, Ремонт и стройка).")

# Команда /send_ad
@dp.message(Command("send_ad"))
async def send_ad_handler(message: types.Message):
    logger.info(f"Получена команда /send_ad от telegram_id={message.from_user.id}")

    # Генерация тестового объявления
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
        "category": CATEGORY,
        "city": CITY,
        "tags": TAG,  # Фиксированный тег "Ремонт и стройка"
        "title_ru": title_ru,
        "description_ru": description_ru,
        "price": price if price else "",  # Пустая строка вместо None
        "contact_info": "@TestSender",
        "status": "pending",
        "is_test": True,
        "api_key": API_KEY,
        "user_id": "test_sender"  # Передаём telegram_id, Froggle найдёт user_id
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
    logger.info("Запуск AdSenderServiceTbilisi...")
    logger.debug("Polling started")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())