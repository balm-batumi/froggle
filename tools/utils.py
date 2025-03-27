from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from database import Advertisement
from loguru import logger
from database import mark_ad_as_viewed
from data.categories import CATEGORIES


# Рендерит объявление с медиа и форматированным текстом
async def render_ad(ad: Advertisement, bot: Bot, chat_id: int, show_status: bool = False,
                    buttons: list[InlineKeyboardButton] = None):
    from database import mark_ad_as_viewed  # Импорт функции для отметки просмотра

    title = ad.title_ru if ad.title_ru else "Без названия"
    description = ad.description_ru if ad.description_ru else "Без описания"
    contact_info = ad.contact_info if ad.contact_info else "Не указаны"
    price = ad.price if ad.price else "без цены"
    status_text = f"Статус: {ad.status}" if show_status and ad.status else ""

    text = (
        f"<b>{CATEGORIES[ad.category]['display_name']}</b> в <b>{ad.city}</b>\n"
        f"🏷️ {', '.join(ad.tags) if ad.tags else 'Нет тегов'}\n"
        f"<b>{title}</b>\n"
        f"{description[:1000] + '...' if len(description) > 1000 else description}\n"
        f"💰 {price}\n"
        f"📞 {contact_info}"
    )
    if status_text:
        text += f"\n{status_text}"

    # Отладка: проверяем, что приходит в buttons
    logger.debug(f"Buttons перед созданием клавиатуры: {buttons}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

    await bot.send_message(
        chat_id=chat_id,
        text=f"•••••••     Объявление #{ad.id}:     •••••••"
    )

    if ad.media_file_ids and len(ad.media_file_ids) > 0:
        if len(ad.media_file_ids) == 1:
            media = ad.media_file_ids[0]
            file_id = media.get("id")
            media_type = media.get("type")
            try:
                if media_type == "photo":
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=file_id,
                        caption=text,
                        reply_markup=keyboard
                    )
                elif media_type == "video":
                    await bot.send_video(
                        chat_id=chat_id,
                        video=file_id,
                        caption=text,
                        reply_markup=keyboard
                    )
                else:
                    logger.error(f"Неизвестный тип медиа {media_type} в объявлении ID {ad.id}")
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"{text}\nОшибка: неизвестный тип медиа",
                        reply_markup=keyboard
                    )
            except Exception as e:
                logger.error(f"Ошибка отправки одиночного медиа {file_id} в объявлении ID {ad.id}: {e}")
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"{text}\nОшибка загрузки медиа",
                    reply_markup=keyboard
                )
        else:
            media_group = []
            for media in ad.media_file_ids[:10]:
                file_id = media.get("id")
                media_type = media.get("type")
                if media_type == "photo":
                    media_group.append(InputMediaPhoto(media=file_id))
                elif media_type == "video":
                    media_group.append(InputMediaVideo(media=file_id))
                else:
                    logger.warning(f"Пропущен файл с неизвестным типом {media_type} в объявлении ID {ad.id}")
                    continue

            try:
                await bot.send_media_group(chat_id=chat_id, media=media_group)
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Ошибка отправки медиа-группы в объявлении ID {ad.id}: {e}")
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"{text}\nОшибка загрузки медиа-группы",
                    reply_markup=keyboard
                )
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard
        )

    # Отмечаем объявление как просмотренное после успешного вывода
    await mark_ad_as_viewed(str(chat_id), ad.id)