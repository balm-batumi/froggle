from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from database import Advertisement
from loguru import logger
from database import mark_ad_as_viewed
from data.categories import CATEGORIES
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Создает клавиатуру с кнопками "Помощь" и "Назад" для навигации
def get_navigation_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Помощь", callback_data="action:help"),
         InlineKeyboardButton(text="Назад", callback_data="action:back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# tools/utils.py
# Отображает объявление, рендерит все фото и видео группами, возвращает список message_id
async def render_ad(ad: Advertisement, bot: Bot, chat_id: int, show_status: bool = False,
                    buttons: list[InlineKeyboardButton] = None, mark_viewed: bool = False):
    message_ids = []

    # Отправляем заголовок со звёздочками
    msg1 = await bot.send_message(chat_id=chat_id, text=f"*****       Объявление #{ad.id}       *****")
    message_ids.append(msg1.message_id)

    # Обработка медиа
    if ad.media_file_ids:
        # Разделяем медиа на фото и видео
        photos = [media for media in ad.media_file_ids if media["type"] == "photo"]
        videos = [media for media in ad.media_file_ids if media["type"] == "video"]

        # Отправляем группу фото (до 10 элементов)
        if photos:
            media_group = [InputMediaPhoto(media=photo["id"]) for photo in photos[:10]]
            photo_msgs = await bot.send_media_group(chat_id=chat_id, media=media_group)
            message_ids.extend(msg.message_id for msg in photo_msgs)
            logger.debug(f"Отправлена группа фото для объявления #{ad.id}, message_ids={[msg.message_id for msg in photo_msgs]}")

        # Отправляем группу видео (до 10 элементов)
        if videos:
            media_group = [InputMediaVideo(media=video["id"]) for video in videos[:10]]
            video_msgs = await bot.send_media_group(chat_id=chat_id, media=media_group)
            message_ids.extend(msg.message_id for msg in video_msgs)
            logger.debug(f"Отправлена группа видео для объявления #{ad.id}, message_ids={[msg.message_id for msg in video_msgs]}")

    # Формируем основной текст с жирным форматированием
    ad_text = f"<b>{CATEGORIES[ad.category]['display_name']}</b> в {ad.city}\n"
    ad_text += f"🏷️ {', '.join(ad.tags)}\n" if ad.tags else ""
    ad_text += f"📌 <b>{ad.title_ru}</b>\n" if ad.title_ru else ""
    ad_text += f"{ad.description_ru}\n" if ad.description_ru else ""
    ad_text += f"💰 {ad.price}\n" if ad.price else "💰 без цены\n"
    ad_text += f"📞 {ad.contact_info}\n" if ad.contact_info else ""
    if show_status:
        ad_text += f"Статус: {ad.status}"

    # Создаём клавиатуру, если переданы кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    logger.debug(f"Buttons перед созданием клавиатуры: {buttons}")

    # Отправляем текст с клавиатурой
    msg3 = await bot.send_message(chat_id=chat_id, text=ad_text, reply_markup=keyboard, parse_mode="HTML")
    message_ids.append(msg3.message_id)

    # Отмечаем как просмотренное, если требуется
    if mark_viewed and ad.id:
        await mark_ad_as_viewed(str(chat_id), ad.id)

    return message_ids