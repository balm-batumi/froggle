# tools/utils.py
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from database import Advertisement
from loguru import logger
from database import mark_ad_as_viewed
from data.categories import CATEGORIES
from typing import List, Optional
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey


# Создает навигационную клавиатуру с кнопками "❓" (Помощь) и "⬅️" (Назад)
def get_navigation_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="❓", callback_data="action:help"),
         InlineKeyboardButton(text="⬅️", callback_data="action:back")]
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


# Утилита для удаления списка сообщений с обработкой ошибок
async def delete_messages(bot: Bot, chat_id: int, message_ids: list[int]) -> None:
    """
    Удаляет сообщения по их ID в указанном чате.

    Args:
        bot: Объект бота для выполнения операций.
        chat_id: ID чата, где нужно удалить сообщения.
        message_ids: Список ID сообщений для удаления.
    """
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            logger.debug(f"Удалено сообщение {msg_id} в чате {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения {msg_id} в чате {chat_id}: {e}")


async def notify_user(bot: Bot, telegram_id: str, text: str, state: FSMContext, reply_markup=None) -> None:
    """
    Отправляет уведомление пользователю, удаляя предыдущее, и сохраняет message_id в состоянии.

    Args:
        bot: Объект бота для отправки сообщения.
        telegram_id: Telegram ID пользователя.
        text: Текст уведомления.
        state: Контекст FSM для сохранения message_id.
        reply_markup: Опциональная клавиатура (по умолчанию None).
    """
    notification_state = FSMContext(
        storage=state.storage,
        key=StorageKey(bot_id=bot.id, chat_id=int(telegram_id), user_id=int(telegram_id))
    )
    current_data = await notification_state.get_data()
    old_message_id = current_data.get("rejection_notification_id")

    if old_message_id:
        try:
            await bot.delete_message(chat_id=telegram_id, message_id=old_message_id)
            logger.debug(f"Удалено старое уведомление message_id={old_message_id} для telegram_id={telegram_id}")
        except Exception as e:
            logger.debug(f"Не удалось удалить старое уведомление message_id={old_message_id}: {e}")

    try:
        msg = await bot.send_message(chat_id=telegram_id, text=text, reply_markup=reply_markup)
        await notification_state.update_data(rejection_notification_id=msg.message_id)
        logger.debug(
            f"Уведомление отправлено telegram_id={telegram_id}, message_id={msg.message_id}, text='{text[:35]}...'")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления telegram_id={telegram_id}: {e}")