from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from database import Advertisement
from loguru import logger
from database import mark_ad_as_viewed
from data.categories import CATEGORIES


async def render_ad(ad: Advertisement, bot: Bot, chat_id: int, show_status: bool = False, buttons: list[InlineKeyboardButton] = None, mark_viewed: bool = False):
    ad_text = f"{CATEGORIES[ad.category]['display_name']} в {ad.city}\n"
    ad_text += f"🏷️ {', '.join(ad.tags)}\n" if ad.tags else ""  # Отображаем все теги
    ad_text += f"{ad.title_ru}\n" if ad.title_ru else ""
    ad_text += f"{ad.description_ru}\n" if ad.description_ru else ""
    ad_text += f"💰 {ad.price}\n" if ad.price else "💰 без цены\n"
    ad_text += f"📞 {ad.contact_info}\n" if ad.contact_info else ""
    if show_status:
        ad_text += f"Статус: {ad.status}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    logger.debug(f"Buttons перед созданием клавиатуры: {buttons}")

    if ad.media_file_ids:
        media = ad.media_file_ids[0]
        if media["type"] == "photo":
            await bot.send_photo(chat_id=chat_id, photo=media["id"], caption=ad_text, reply_markup=keyboard)
    else:
        await bot.send_message(chat_id=chat_id, text=ad_text, reply_markup=keyboard)

    if mark_viewed and ad.id:
        await mark_ad_as_viewed(str(chat_id), ad.id)