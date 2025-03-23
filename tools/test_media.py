import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from loguru import logger
from config import BOT_TOKEN  # Импорт токена из config.py

# Настройка логирования
logger.add("test_media.log", rotation="10MB", compression="zip", level="DEBUG")

# Определяем состояния
class TestForm(StatesGroup):
    media = State()

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# Обработчик команды /start
@dp.message(F.text == "/start")
async def start_handler(message: types.Message, state: FSMContext):
    await state.set_state(TestForm.media)
    await state.update_data(category="Тестовая категория", media_file_ids=[], media_groups={}, last_group_time=0)
    await message.answer("Отправьте фото или видео (одиночные или группой) для теста.")

# Обработчик медиа
@dp.message(F.photo | F.video, StateFilter(TestForm.media))
async def process_media(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id if message.photo else message.video.file_id
    media_group_id = message.media_group_id
    data = await state.get_data()
    media_file_ids = data.get("media_file_ids", [])
    media_message_id = data.get("media_message_id")
    media_groups = data.get("media_groups", {})
    last_group_time = data.get("last_group_time", 0)
    current_time = asyncio.get_event_loop().time()
    logger.debug(f"Начало обработки: file_count={len(media_file_ids)}, media_message_id={media_message_id}, media_group_id={media_group_id}")

    if file_id not in media_file_ids:
        media_file_ids.append(file_id)
        if media_group_id:
            # Накопление файлов группы
            group_files = media_groups.get(media_group_id, [])
            group_files.append(file_id)
            media_groups[media_group_id] = group_files
            await state.update_data(media_file_ids=media_file_ids, media_groups=media_groups, last_group_time=current_time)
            logger.debug(f"Добавлен файл в группу: {media_group_id}, files={group_files}")

            # Ждем 1 секунду после последнего файла группы
            await asyncio.sleep(1)
            data = await state.get_data()
            if data.get("last_group_time") == current_time:  # Если время не обновилось, это последний файл
                file_count = len(media_file_ids)
                text = f"Загружено {file_count} файлов" if file_count > 1 else f"Загружено {file_count} файл"
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Подтвердите", callback_data="confirm_media"),
                     InlineKeyboardButton(text="Пропустить", callback_data="skip_media")],
                    [InlineKeyboardButton(text="Помощь", callback_data="help_media")]
                ])

                try:
                    if not media_message_id:
                        msg = await message.answer(text, reply_markup=keyboard)
                        await state.update_data(media_message_id=msg.message_id)
                        logger.debug(f"Создано сообщение: message_id={msg.message_id}, text='{text}'")
                    else:
                        await message.bot.edit_message_text(
                            text=text,
                            chat_id=message.chat.id,
                            message_id=media_message_id,
                            reply_markup=keyboard
                        )
                        logger.debug(f"Отредактировано сообщение: message_id={media_message_id}, text='{text}'")
                except Exception as e:
                    logger.error(f"Ошибка: {e}")
                    await message.answer("Ошибка при обработке медиа.")
        else:
            # Одиночный файл
            file_count = len(media_file_ids)
            text = f"Загружено {file_count} файлов" if file_count > 1 else f"Загружено {file_count} файл"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Подтвердите", callback_data="confirm_media"),
                 InlineKeyboardButton(text="Пропустить", callback_data="skip_media")],
                [InlineKeyboardButton(text="Помощь", callback_data="help_media")]
            ])

            try:
                if not media_message_id:
                    msg = await message.answer(text, reply_markup=keyboard)
                    await state.update_data(media_message_id=msg.message_id)
                    logger.debug(f"Создано сообщение: message_id={msg.message_id}, text='{text}'")
                else:
                    await message.bot.edit_message_text(
                        text=text,
                        chat_id=message.chat.id,
                        message_id=media_message_id,
                        reply_markup=keyboard
                    )
                    logger.debug(f"Отредактировано сообщение: message_id={media_message_id}, text='{text}'")
            except Exception as e:
                logger.error(f"Ошибка: {e}")
                await message.answer("Ошибка при обработке медиа.")

# Обработчик подтверждения
@dp.callback_query(F.data == "confirm_media", StateFilter(TestForm.media))
async def confirm_media(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    file_count = len(data.get("media_file_ids", []))
    await call.message.edit_text(f"Загружено {file_count} файлов. Завершено!")
    await state.clear()
    await call.answer()

# Обработчик пропуска
@dp.callback_query(F.data == "skip_media", StateFilter(TestForm.media))
async def skip_media(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Медиа пропущены.")
    await state.clear()
    await call.answer()

# Обработчик помощи
@dp.callback_query(F.data == "help_media", StateFilter(TestForm.media))
async def help_media(call: types.CallbackQuery):
    await call.message.bot.send_message(call.from_user.id, "Отправляйте фото/видео, затем подтвердите или пропустите.")
    await call.answer()

# Запуск бота
async def main():
    logger.info("Запуск тестового бота...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())