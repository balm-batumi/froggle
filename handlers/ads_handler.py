from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram import F
from sqlalchemy import select, func
from loguru import logger
from database import get_db, Advertisement, get_cities, get_category_tags, is_favorite, User
from database import is_favorite, add_to_favorites
from data.constants import get_main_menu_keyboard
from handlers.ad_handler import AD_CATEGORIES
from states import AdsViewForm, AdAddForm

ads_router = Router()

# Обработка выбора категории из главного меню
@ads_router.callback_query(F.data.startswith("category:"))
async def show_cities_by_category(call: types.CallbackQuery, state: FSMContext):
    category = call.data.split(":")[1]
    telegram_id = str(call.from_user.id)
    logger.info(f"Пользователь {telegram_id} выбрал категорию '{category}' для просмотра объявлений")

    async for session in get_db():
        city_counts = await session.execute(
            select(Advertisement.city, func.count(Advertisement.id).label("count"))
            .where(Advertisement.category == category, Advertisement.status == "approved")
            .group_by(Advertisement.city)
            .order_by(func.count(Advertisement.id).desc())
        )
        cities = city_counts.all()

        if not cities:
            await call.message.edit_text(
                f"В категории '{category}' пока нет одобренных объявлений.\n🏠:",
                reply_markup=get_main_menu_keyboard()
            )
            await state.clear()
            await call.answer()
            return

        buttons = [
            InlineKeyboardButton(text=f"{city} ({count})", callback_data=f"city_select:{category}:{city}")
            for city, count in cities if city
        ]
        keyboard_rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
        # Добавляем строку с кнопками "Помощь", "Добавить своё", "Назад"
        keyboard_rows.append([
            InlineKeyboardButton(text="Помощь", callback_data="action:help"),
            InlineKeyboardButton(text="Добавить своё", callback_data="action:add"),
            InlineKeyboardButton(text="Назад", callback_data="action:back")
        ])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

        await state.update_data(category=category)
        await call.message.edit_text(
            f"Выберите город для просмотра объявлений в категории '{category}':",
            reply_markup=keyboard
        )
        await state.set_state(AdsViewForm.select_city)
        await call.answer()


# Обработка выбора города для просмотра
@ads_router.callback_query(F.data.startswith("city_select:"), StateFilter(AdsViewForm.select_city))
async def show_ads_by_city(call: types.CallbackQuery, state: FSMContext):
    _, category, city = call.data.split(":", 2)
    telegram_id = str(call.from_user.id)
    logger.info(f"Пользователь {telegram_id} выбрал город '{city}' в категории '{category}'")

    async for session in get_db():
        ads = await session.execute(
            select(Advertisement)
            .where(Advertisement.category == category, Advertisement.city == city, Advertisement.status == "approved")
            .order_by(Advertisement.id)
        )
        ads = ads.scalars().all()

        if not ads:
            logger.debug(f"Нет объявлений для города '{city}' в категории '{category}'")
            await call.message.edit_text(
                f"В городе '{city}' категории '{category}' нет одобренных объявлений.\n🏠:",
                reply_markup=get_main_menu_keyboard()
            )
            await state.clear()
            await call.answer()
            return

        logger.debug(f"Начало вывода объявлений. Количество: {len(ads)}")
        await call.message.delete()
        header_text = f"🔹 <b>{category}</b> в городе <b>{city}</b> 🔹"
        underline = "―" * 30
        header_msg = await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text=f"{header_text}\n{underline}"
        )
        logger.debug(f"Отправлен заголовок, message_id: {header_msg.message_id}")
        filter_msg = await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text="Временно фильтрация по тегам отключена"
        )
        logger.debug(f"Отправлено сообщение о фильтрации, message_id: {filter_msg.message_id}")

        for index, ad in enumerate(ads):
            text = (
                f"#{ad.id}\n"
                f"📌 {', '.join(ad.tags) if ad.tags else 'Нет тегов'}\n"
                f"{ad.title_ru}\n"
                f"{ad.description_ru[:1000] + '...' if len(ad.description_ru) > 1000 else ad.description_ru}\n"
                f"контакты: {ad.contact_info if ad.contact_info else 'Не указаны'}"
            )
            logger.debug(f"Текст объявления ID {ad.id}: {repr(text)}")
            # Проверка, в избранном ли объявление
            user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = user_result.scalar_one_or_none()
            is_fav = await is_favorite(user.id, ad.id) if user else False
            logger.debug(f"Объявление ID {ad.id} в избранном: {is_fav}")

            # Кнопка "В избранное" или уведомление
            favorite_button = InlineKeyboardButton(
                text="В избранное" if not is_fav else "Уже в избранном",
                callback_data=f"favorite:add:{ad.id}" if not is_fav else "favorite:already"
            )
            ad_keyboard = InlineKeyboardMarkup(inline_keyboard=[[favorite_button]])
            logger.debug(f"Создана клавиатура для ID {ad.id}: {ad_keyboard.inline_keyboard}")

            if ad.media_file_ids and len(ad.media_file_ids) > 0:
                if len(ad.media_file_ids) == 1:
                    try:
                        msg = await call.message.bot.send_photo(
                            chat_id=call.from_user.id,
                            photo=ad.media_file_ids[0],
                            caption=text,
                            reply_markup=ad_keyboard
                        )
                        logger.debug(f"Отправлено фото для ID {ad.id}, message_id: {msg.message_id}")
                    except Exception as e:
                        if "can't use file of type Video as Photo" in str(e):
                            msg = await call.message.bot.send_video(
                                chat_id=call.from_user.id,
                                video=ad.media_file_ids[0],
                                caption=text,
                                reply_markup=ad_keyboard
                            )
                            logger.debug(f"Отправлено видео для ID {ad.id}, message_id: {msg.message_id}")
                        else:
                            logger.error(f"Ошибка отправки медиа для объявления ID {ad.id}: {e}")
                            msg = await call.message.bot.send_message(
                                chat_id=call.from_user.id,
                                text=f"{text}\n⚠ Ошибка загрузки медиа",
                                reply_markup=ad_keyboard
                            )
                            logger.debug(f"Отправлено сообщение с ошибкой для ID {ad.id}, message_id: {msg.message_id}")
                else:
                    media_group = [
                        types.InputMediaPhoto(media=file_id)
                        for file_id in ad.media_file_ids[:10]
                    ]
                    logger.debug(f"Создана медиа-группа для ID {ad.id}, файлов: {len(media_group)}")
                    sent_media = await call.message.bot.send_media_group(
                        chat_id=call.from_user.id,
                        media=media_group
                    )
                    logger.debug(f"Отправлена медиа-группа для ID {ad.id}, message_ids: {[m.message_id for m in sent_media]}")
                    msg = await call.message.bot.send_message(
                        chat_id=call.from_user.id,
                        text=text,
                        reply_markup=ad_keyboard
                    )
                    logger.debug(f"Отправлен текст с клавиатурой для медиа-группы ID {ad.id}, message_id: {msg.message_id}")
            else:
                msg = await call.message.bot.send_message(
                    chat_id=call.from_user.id,
                    text=text,
                    reply_markup=ad_keyboard
                )
                logger.debug(f"Отправлен текст без медиа для ID {ad.id}, message_id: {msg.message_id}")

            # Добавляем разделитель •••, если это не последнее объявление
            if index < len(ads) - 1:
                sep_msg = await call.message.bot.send_message(
                    chat_id=call.from_user.id,
                    text="•••"
                )
                logger.debug(f"Отправлен разделитель для ID {ad.id}, message_id: {sep_msg.message_id}")

        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Помощь", callback_data="action:help"),
            InlineKeyboardButton(text="Добавить своё", callback_data="action:add"),
            InlineKeyboardButton(text="Назад", callback_data="action:back")
        ]])
        final_msg = await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text="Выберите действие:",
            reply_markup=keyboard
        )
        logger.debug(f"Отправлено финальное меню, message_id: {final_msg.message_id}")
    await call.answer()


@ads_router.callback_query(F.data.startswith("favorite:"), StateFilter(AdsViewForm.select_city))
async def handle_favorite_action(call: types.CallbackQuery, state: FSMContext):
    telegram_id = str(call.from_user.id)
    parts = call.data.split(":")
    action = parts[1]  # "add" или "already"

    async for session in get_db():
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()
        if not user:
            await call.answer("Пользователь не найден. Используйте /start.", show_alert=True)
            return

        if action == "add":
            ad_id = int(parts[2])  # Извлекаем ad_id только для "add"
            if await is_favorite(user.id, ad_id):
                await call.answer("Это объявление уже в вашем избранном!", show_alert=True)
            else:
                await add_to_favorites(user.id, ad_id)
                logger.info(f"Пользователь {telegram_id} добавил объявление #{ad_id} в избранное")
                await call.answer("Добавлено в избранное!", show_alert=True)
        elif action == "already":
            await call.answer("Это объявление уже в вашем избранном!", show_alert=True)



# Обработка действий
@ads_router.callback_query(F.data == "action:help", StateFilter(AdsViewForm.select_city))
async def show_help(call: types.CallbackQuery, state: FSMContext):
    await call.message.bot.send_message(
        chat_id=call.from_user.id,
        text="Froggle — ваш помощник. Здесь вы можете просматривать объявления, добавлять свои или вернуться в меню.\n🏠:",
        reply_markup=get_main_menu_keyboard()
    )
    await state.clear()
    await call.answer()


@ads_router.callback_query(F.data == "action:add", StateFilter(AdsViewForm.select_city))
async def start_adding_ad(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    category = data.get("category")
    telegram_id = str(call.from_user.id)
    logger.info(f"Начало добавления объявления в категории {category} для telegram_id={telegram_id}")

    await state.set_state(AdAddForm.city)
    await state.update_data(category=category)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Тбилиси", callback_data=f"add_city:{category}:Тбилиси"),
         InlineKeyboardButton(text="Батуми", callback_data=f"add_city:{category}:Батуми")],
        [InlineKeyboardButton(text="Кутаиси", callback_data=f"add_city:{category}:Кутаиси"),
         InlineKeyboardButton(text="Гори", callback_data=f"add_city:{category}:Гори")],
        [InlineKeyboardButton(text="Другой город", callback_data=f"add_city_other:{category}"),
         InlineKeyboardButton(text="Помощь", callback_data=f"help:{category}:city"),
         InlineKeyboardButton(text="Назад", callback_data="action:back")]
    ])
    await call.message.bot.send_message(
        chat_id=call.from_user.id,
        text=AD_CATEGORIES[category]["texts"]["city"],
        reply_markup=keyboard
    )
    await call.answer()

@ads_router.callback_query(F.data.startswith("action:back"), StateFilter(AdsViewForm.select_city))
async def back_to_menu(call: types.CallbackQuery, state: FSMContext):
    await call.message.bot.send_message(
        chat_id=call.from_user.id,
        text="Возврат в главное меню 🏠:",
        reply_markup=get_main_menu_keyboard()
    )
    await state.clear()
    await call.answer()

# Обработка выбора города для добавления
@ads_router.callback_query(F.data.startswith("add_city:"), StateFilter(AdAddForm.city))
async def process_add_city(call: types.CallbackQuery, state: FSMContext):
    _, category, city = call.data.split(":", 2)
    telegram_id = str(call.from_user.id)
    logger.info(f"Пользователь {telegram_id} выбрал город '{city}' для добавления в категории '{category}'")

    await state.update_data(city=city)
    tags = await get_category_tags(AD_CATEGORIES[category]["tag_category"])
    if not tags:
        await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text="Нет доступных тегов. Обратитесь к администратору.\n🏠:",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        await call.answer()
        return

    buttons = [[InlineKeyboardButton(text=name, callback_data=f"tag_select:{id}")] for id, name in tags]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await call.message.edit_text(
        AD_CATEGORIES[category]["texts"]["tags"],
        reply_markup=keyboard
    )
    await state.set_state(AdAddForm.tags)
    await call.answer()

# Обработка "Ввести другой город"
@ads_router.callback_query(F.data.startswith("add_city_other:"), StateFilter(AdAddForm.city))
async def process_add_city_other(call: types.CallbackQuery, state: FSMContext):
    category = call.data.split(":", 1)[1]
    telegram_id = str(call.from_user.id)
    logger.info(f"Пользователь {telegram_id} выбрал 'Другой город' для категории '{category}'")

    cities = await get_cities()
    main_cities = ["Тбилиси", "Батуми", "Кутаиси", "Гори"]
    other_cities = [city[1] for city in cities if city[1] not in main_cities]
    buttons = [
        InlineKeyboardButton(text=city, callback_data=f"add_city:{category}:{city}")
        for city in other_cities
    ]
    keyboard_rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await call.message.edit_text(
        "Выберите другой город:",
        reply_markup=keyboard
    )
    await call.answer()