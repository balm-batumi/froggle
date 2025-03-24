from aiogram import Router, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from states import MenuState, AdAddForm
from database import get_db, User, select, Favorite, Advertisement, remove_from_favorites
from data.constants import get_main_menu_keyboard
from data.categories import CATEGORIES
from loguru import logger

menu_router = Router()

# Клавиатура подменю для категорий
ad_start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Добавить своё")],
        [KeyboardButton(text="Помощь"), KeyboardButton(text="Назад")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

@menu_router.message(Command("start"))
async def start_handler(message: types.Message):
    telegram_id = str(message.from_user.id)
    logger.info(f"Получена команда /start от telegram_id={telegram_id}")

    async for session in get_db():
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            new_user = User(
                telegram_id=telegram_id,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                username=message.from_user.username
            )
            session.add(new_user)
            await session.commit()
            logger.info(f"Добавлен новый пользователь с telegram_id={telegram_id}")
        else:
            logger.debug(f"Пользователь с telegram_id={telegram_id} уже существует")

    await message.answer(
        "Добро пожаловать в Froggle! Выберите категорию:",
        reply_markup=get_main_menu_keyboard()
    )

@menu_router.callback_query(lambda call: call.data == "action:help")
async def help_handler(call: types.CallbackQuery):
    await call.message.edit_text(
        "Froggle — ваш помощник. Выберите категорию для просмотра объявлений.",
        reply_markup=get_main_menu_keyboard()
    )
    await call.answer()

# Настройки
@menu_router.callback_query(lambda call: call.data == "action:settings")
async def settings_handler(call: types.CallbackQuery):
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user and user.is_admin:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Модерация", callback_data="admin_moderate")],
                [InlineKeyboardButton(text="Избранное", callback_data="show_favorites")],
                [InlineKeyboardButton(text="Мои", callback_data="show_my_ads")],
                [InlineKeyboardButton(text="Назад", callback_data="action:back")]
            ])
            await call.message.edit_text("Настройки для админа:", reply_markup=keyboard)
        else:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Избранное", callback_data="show_favorites")],
                [InlineKeyboardButton(text="Мои", callback_data="show_my_ads")],
                [InlineKeyboardButton(text="Назад", callback_data="action:back")]
            ])
            await call.message.edit_text("Ваши настройки:", reply_markup=keyboard)
    await call.answer()

# Показать объявления пользователя
@menu_router.callback_query(lambda call: call.data == "show_my_ads")
async def show_my_ads_handler(call: types.CallbackQuery):
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()
        if not user:
            await call.message.edit_text("Пользователь не найден. Используйте /start.", reply_markup=get_main_menu_keyboard())
            return

        ads_result = await session.execute(
            select(Advertisement)
            .where(Advertisement.user_id == user.id, Advertisement.status.in_(["approved", "pending"]))
            .order_by(Advertisement.id)
        )
        ads = ads_result.scalars().all()

        if not ads:
            await call.message.edit_text("У вас нет активных объявлений.\n:", reply_markup=get_main_menu_keyboard())
            return

        await call.message.delete()
        await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text="Ваши объявления\n" + "―" * 27
        )

        for ad in ads:
            title = ad.title_ru if ad.title_ru else "Без названия"
            description = ad.description_ru if ad.description_ru else "Без описания"
            contact_info = ad.contact_info if ad.contact_info else "Не указаны"
            display_name = CATEGORIES[ad.category]["display_name"]
            text = (
                f"<b>{display_name} в {ad.city}</b>\n"
                f"📌 {', '.join(ad.tags) if ad.tags else 'Нет тегов'}\n"
                f"{title}\n"
                f"{description[:1000] + '...' if len(description) > 1000 else description}\n"
                f"контакты: {contact_info}\n"
                f"Статус: {ad.status}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Удалить", callback_data=f"delete_ad:{ad.id}")]
            ])

            await call.message.bot.send_message(
                chat_id=call.from_user.id,
                text=f"•••••     Объявление #{ad.id}:     •••••"
            )

            if ad.media_file_ids and len(ad.media_file_ids) > 0:
                photo_group = []
                video_group = []
                for file_id in ad.media_file_ids[:10]:
                    try:
                        file_info = await call.message.bot.get_file(file_id)
                        file_path = file_info.file_path.lower()
                        if file_path.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                            photo_group.append(types.InputMediaPhoto(media=file_id))
                        elif file_path.endswith(('.mp4', '.mov', '.avi')):
                            video_group.append(types.InputMediaVideo(media=file_id))
                        else:
                            logger.warning(f"Неизвестный тип файла для file_id {file_id}: {file_path}")
                    except Exception as e:
                        logger.error(f"Ошибка при получении file_id {file_id} для объявления ID {ad.id}: {e}")

                if photo_group:
                    if len(photo_group) == 1:
                        await call.message.bot.send_photo(
                            chat_id=call.from_user.id,
                            photo=photo_group[0].media
                        )
                    else:
                        await call.message.bot.send_media_group(chat_id=call.from_user.id, media=photo_group)
                if video_group:
                    if len(video_group) == 1:
                        await call.message.bot.send_video(
                            chat_id=call.from_user.id,
                            video=video_group[0].media
                        )
                    else:
                        await call.message.bot.send_media_group(chat_id=call.from_user.id, media=video_group)

            await call.message.bot.send_message(chat_id=call.from_user.id, text=text, reply_markup=keyboard)

        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="action:settings")]
        ])
        await call.message.bot.send_message(chat_id=call.from_user.id, text="Вернуться в настройки:", reply_markup=back_keyboard)
    await call.answer()


# Удаление объявления
@menu_router.callback_query(lambda call: call.data.startswith("delete_ad:"))
async def delete_ad_handler(call: types.CallbackQuery):
    telegram_id = str(call.from_user.id)
    ad_id = int(call.data.split(":")[1])

    async for session in get_db():
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()
        if not user:
            await call.answer("Пользователь не найден.", show_alert=True)
            return

        ad_result = await session.execute(
            select(Advertisement).where(Advertisement.id == ad_id, Advertisement.user_id == user.id)
        )
        ad = ad_result.scalar_one_or_none()
        if not ad:
            await call.answer("Объявление не найдено или вам не принадлежит.", show_alert=True)
            return

        ad.status = "deleted"
        await session.commit()
        logger.info(f"Пользователь {telegram_id} пометил объявление #{ad_id} как удалённое")

        await call.answer("Объявление помечено как удалённое!", show_alert=True)
        await call.message.bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)

        if user.is_admin:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Модерация", callback_data="admin_moderate")],
                [InlineKeyboardButton(text="Избранное", callback_data="show_favorites")],
                [InlineKeyboardButton(text="Мои", callback_data="show_my_ads")],
                [InlineKeyboardButton(text="Назад", callback_data="action:back")]
            ])
            await call.message.bot.send_message(
                chat_id=call.from_user.id,
                text="Настройки для админа:",
                reply_markup=keyboard
            )
        else:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Избранное", callback_data="show_favorites")],
                [InlineKeyboardButton(text="Мои", callback_data="show_my_ads")],
                [InlineKeyboardButton(text="Назад", callback_data="action:back")]
            ])
            await call.message.bot.send_message(
                chat_id=call.from_user.id,
                text="Ваши настройки:",
                reply_markup=keyboard
            )

# Показать избранное
@menu_router.callback_query(lambda call: call.data == "show_favorites")
async def show_favorites_handler(call: types.CallbackQuery):
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()
        if not user:
            await call.message.edit_text("Пользователь не найден. Используйте /start.", reply_markup=get_main_menu_keyboard())
            return

        favorites = await session.execute(
            select(Favorite).where(Favorite.user_id == user.id)
        )
        favorites = favorites.scalars().all()

        if not favorites:
            await call.message.bot.send_message(
                chat_id=call.from_user.id,
                text="У вас нет избранных объявлений.\n:", reply_markup=get_main_menu_keyboard()
            )
            return

        await call.message.delete()
        await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text="Ваши избранные объявления\n" + "―" * 27
        )

        for fav in favorites:
            ad_result = await session.execute(
                select(Advertisement).where(Advertisement.id == fav.advertisement_id)
            )
            ad = ad_result.scalar_one_or_none()
            if ad:
                title = ad.title_ru if ad.title_ru else "Без названия"
                description = ad.description_ru if ad.description_ru else "Без описания"
                contact_info = ad.contact_info if ad.contact_info else "Не указаны"
                status_text = "Удалено автором" if ad.status == "deleted" else ""
                display_name = CATEGORIES[ad.category]["display_name"]
                text = (
                    f"<b>{display_name} в {ad.city}</b>\n"
                    f"📌 {', '.join(ad.tags) if ad.tags else 'Нет тегов'}\n"
                    f"{title}\n"
                    f"{description[:1000] + '...' if len(description) > 1000 else description}\n"
                    f"контакты: {contact_info}\n"
                    f"{status_text}"
                )
                remove_button = InlineKeyboardButton(
                    text="Удалить из избранного",
                    callback_data=f"favorite:remove:{ad.id}"
                )
                fav_keyboard = InlineKeyboardMarkup(inline_keyboard=[[remove_button]])

                await call.message.bot.send_message(
                    chat_id=call.from_user.id,
                    text=f"•••••     Объявление #{ad.id}:     •••••"
                )

                if ad.media_file_ids and len(ad.media_file_ids) > 0:
                    photo_group = []
                    video_group = []
                    for file_id in ad.media_file_ids[:10]:
                        try:
                            file_info = await call.message.bot.get_file(file_id)
                            file_path = file_info.file_path.lower()
                            if file_path.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                                photo_group.append(types.InputMediaPhoto(media=file_id))
                            elif file_path.endswith(('.mp4', '.mov', '.avi')):
                                video_group.append(types.InputMediaVideo(media=file_id))
                            else:
                                logger.warning(f"Неизвестный тип файла для file_id {file_id}: {file_path}")
                        except Exception as e:
                            logger.error(f"Ошибка при получении file_id {file_id} для объявления ID {ad.id}: {e}")

                    if photo_group:
                        if len(photo_group) == 1:
                            await call.message.bot.send_photo(
                                chat_id=call.from_user.id,
                                photo=photo_group[0].media
                            )
                        else:
                            await call.message.bot.send_media_group(chat_id=call.from_user.id, media=photo_group)
                    if video_group:
                        if len(video_group) == 1:
                            await call.message.bot.send_video(
                                chat_id=call.from_user.id,
                                video=video_group[0].media
                            )
                        else:
                            await call.message.bot.send_media_group(chat_id=call.from_user.id, media=video_group)

                await call.message.bot.send_message(
                    chat_id=call.from_user.id,
                    text=text,
                    reply_markup=fav_keyboard
                )
            else:
                text = f"Объявление больше не доступно"
                remove_button = InlineKeyboardButton(
                    text="Удалить из избранного",
                    callback_data=f"favorite:remove:{fav.advertisement_id}"
                )
                fav_keyboard = InlineKeyboardMarkup(inline_keyboard=[[remove_button]])
                await call.message.bot.send_message(
                    chat_id=call.from_user.id,
                    text=f"•••••     Объявление #{fav.advertisement_id}:     •••••"
                )
                await call.message.bot.send_message(
                    chat_id=call.from_user.id,
                    text=text,
                    reply_markup=fav_keyboard
                )

        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Назад", callback_data="action:settings")]
        ])
        await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text="Вернуться в настройки:",
            reply_markup=back_keyboard
        )
    await call.answer()


# Удаление из избранного
@menu_router.callback_query(lambda call: call.data.startswith("favorite:remove:"))
async def remove_from_favorites_handler(call: types.CallbackQuery):
    telegram_id = str(call.from_user.id)
    _, action, ad_id = call.data.split(":", 2)
    ad_id = int(ad_id)

    async for session in get_db():
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()
        if not user:
            await call.answer("Пользователь не найден.", show_alert=True)
            return

        if await remove_from_favorites(user.id, ad_id):
            logger.info(f"Пользователь {telegram_id} удалил объявление #{ad_id} из избранного")
            await call.answer("Удалено из избранного!", show_alert=True)
        else:
            await call.answer("Объявление не найдено в избранном.", show_alert=True)

    await show_favorites_handler(call)

@menu_router.callback_query(lambda call: call.data == "action:back")
async def back_handler(call: types.CallbackQuery):
    await call.message.edit_text(
        "Возврат в главное меню :",
        reply_markup=get_main_menu_keyboard()
    )
    await call.answer()