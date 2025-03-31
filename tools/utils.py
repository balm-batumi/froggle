# tools/utils.py
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from database import Advertisement
from loguru import logger
from database import mark_ad_as_viewed
from data.categories import CATEGORIES
from typing import List, Optional


# Создает клавиатуру с кнопками "Помощь" и "Назад" для навигации
def get_navigation_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Помощь", callback_data="action:help"),
         InlineKeyboardButton(text="Назад", callback_data="action:back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_ad_text(ad: Advertisement, fields: Optional[List[str]] = None, complete: bool = True,
                   show_status: bool = False) -> str | List[str]:
    """
    Формирует текст объявления поэтапно или целиком.

    Args:
        ad: Объект объявления.
        fields: Список новых полей для включения (например, ['title', 'description']). Если None и complete=False, только базовые поля.
        complete: Если True, полный текст как строка. Если False, список строк для заполнения.
        show_status: Показывать ли статус (для модерации).

    Returns:
        str: Полный текст (complete=True).
        List[str]: Список строк (complete=False).
    """
    lines = []

    # Базовые поля, которые всегда есть при создании
    if ad.category:
        lines.append(f"<b>{CATEGORIES[ad.category]['display_name']}</b>")
    if ad.city:
        lines.append(f"в {ad.city}")
    if ad.tags:
        lines.append(f"🏷️ {', '.join(ad.tags) if ad.tags else 'Нет тегов'}")

    # Добавляем новые поля, если указаны
    fields_to_render = fields if fields else []
    if 'title' in fields_to_render and ad.title_ru:
        lines.append(f"📌 <b>{ad.title_ru}</b>")
    if 'description' in fields_to_render and ad.description_ru:
        lines.append(ad.description_ru)
    if 'price' in fields_to_render:
        lines.append(f"💰 {ad.price}" if ad.price else "💰 без цены")
    if 'contacts' in fields_to_render and ad.contact_info:
        lines.append(f"📞 {ad.contact_info}")
    if 'status' in fields_to_render and show_status and ad.status:
        lines.append(f"Статус: {ad.status}")

    # В режиме полного рендера добавляем все доступные поля
    if complete:
        if ad.title_ru and 'title' not in fields_to_render:
            lines.append(f"📌 <b>{ad.title_ru}</b>")
        if ad.description_ru and 'description' not in fields_to_render:
            lines.append(ad.description_ru)
        if 'price' not in fields_to_render:
            lines.append(f"💰 {ad.price}" if ad.price else "💰 без цены")
        if ad.contact_info and 'contacts' not in fields_to_render:
            lines.append(f"📞 {ad.contact_info}")
        if show_status and ad.status and 'status' not in fields_to_render:
            lines.append(f"Статус: {ad.status}")
        return "\n".join(lines)

    return lines


# Отображает объявление, рендерит все фото и видео группами, возвращает список message_id
async def render_ad(ad: Advertisement, bot: Bot, chat_id: int, show_status: bool = False,
                    buttons: list[InlineKeyboardButton] = None, mark_viewed: bool = False):
    message_ids = []

    # Отправляем заголовок со звёздочками
    msg1 = await bot.send_message(chat_id=chat_id, text=f"*****       Объявление #{ad.id}       *****")
    message_ids.append(msg1.message_id)

    # Обработка медиа
    if ad.media_file_ids:
        photos = [media for media in ad.media_file_ids if media["type"] == "photo"]
        videos = [media for media in ad.media_file_ids if media["type"] == "video"]

        if photos:
            media_group = [InputMediaPhoto(media=photo["id"]) for photo in photos[:10]]
            photo_msgs = await bot.send_media_group(chat_id=chat_id, media=media_group)
            message_ids.extend(msg.message_id for msg in photo_msgs)
            logger.debug(
                f"Отправлена группа фото для объявления #{ad.id}, message_ids={[msg.message_id for msg in photo_msgs]}")

        if videos:
            media_group = [InputMediaVideo(media=video["id"]) for video in videos[:10]]
            video_msgs = await bot.send_media_group(chat_id=chat_id, media=media_group)
            message_ids.extend(msg.message_id for msg in video_msgs)
            logger.debug(
                f"Отправлена группа видео для объявления #{ad.id}, message_ids={[msg.message_id for msg in video_msgs]}")

    # Формируем основной текст
    ad_text = format_ad_text(ad, complete=True, show_status=show_status)

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