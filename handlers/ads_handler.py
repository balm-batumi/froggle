from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy import select, func
from loguru import logger
from database import get_db, Advertisement, get_cities, get_category_tags, is_favorite, User, add_to_favorites, Tag, ViewedAds
from data.constants import get_main_menu_keyboard
from data.categories import CATEGORIES
from tools.utils import render_ad
from states import AdsViewForm, AdAddForm

ads_router = Router()


# Обработчик выбора категории для показа городов или сообщения об отсутствии объявлений
@ads_router.callback_query(F.data.startswith("category:"), StateFilter(AdsViewForm.select_category))
async def show_cities_by_category(call: types.CallbackQuery, state: FSMContext):
    logger.debug(f"Хэндлер show_cities_by_category вызван: data={call.data}, state={await state.get_state()}")
    category = call.data.split(":", 1)[1]
    telegram_id = str(call.from_user.id)
    logger.info(f"Пользователь {telegram_id} выбрал категорию '{category}' для просмотра объявлений")
    cities = await get_cities(category)
    if not cities:
        display_name = CATEGORIES[category]["display_name"]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Помощь", callback_data="action:help"),
                InlineKeyboardButton(text="Добавить своё", callback_data="action:add"),
                InlineKeyboardButton(text="Назад", callback_data="action:back")
            ]
        ])
        await state.update_data(category=category)
        await call.message.edit_text(
            f"В категории '{display_name}' нет одобренных объявлений",
            reply_markup=keyboard
        )
        await call.answer()
        return

    city_list = [(city, count) for city, count in cities.items()]
    buttons = [city_list[i:i + 3] for i in range(0, len(city_list), 3)]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{city} ({count})",
            callback_data=f"city_select:{category}:{city}"
        ) for city, count in row] for row in buttons
    ] + [[
        InlineKeyboardButton(text="Помощь", callback_data="action:help"),
        InlineKeyboardButton(text="Добавить своё", callback_data="action:add"),
        InlineKeyboardButton(text="Назад", callback_data="action:back")
    ]])
    await call.message.edit_text(
        "Выберите город для просмотра объявлений:",
        reply_markup=keyboard
    )
    await state.update_data(category=category)
    await state.set_state(AdsViewForm.select_city)
    await call.answer()


# Показывает теги для фильтрации объявлений после выбора города
# Логирует состояние для проверки корректности FSM
@ads_router.callback_query(F.data.startswith("city_select:"), StateFilter(AdsViewForm.select_city))
async def show_ads_by_city(call: types.CallbackQuery, state: FSMContext):
    logger.debug(f"show_ads_by_city: Начало обработки для telegram_id={call.from_user.id}, data={call.data}")
    _, category, city = call.data.split(":", 2)
    telegram_id = str(call.from_user.id)
    logger.info(f"Пользователь {telegram_id} выбрал город '{city}' в категории '{category}'")
    await state.update_data(category=category, city=city)
    logger.debug(f"Начало получения тегов для category='{category}', city='{city}'")
    tags = await get_category_tags(category, city)
    logger.debug(f"Получены теги: {tags}")
    if not tags:
        logger.debug(f"Нет тегов для категории '{category}' в городе '{city}'")
        await call.message.edit_text(
            "Нет доступных тегов для фильтрации.\n:",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        await call.answer()
        return

    buttons = [tags[i:i + 3] for i in range(0, len(tags), 3)]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"tag:{id}") for id, name in row] for row in buttons
    ])
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="Только новые", callback_data="only_new"),
        InlineKeyboardButton(text="Найти", callback_data="skip")
    ])
    await call.message.edit_text(
        f"Выберите теги для фильтрации в {city} (или нажмите Найти для поиска без фильтров):",
        reply_markup=keyboard
    )
    await state.set_state(AdsViewForm.select_tags)
    logger.debug(f"show_ads_by_city: telegram_id={telegram_id}, установленное состояние={await state.get_state()}")
    await call.answer()


# Обрабатывает выбор тегов и выводит отфильтрованные объявления
# Логирует ключевые этапы и очищает старые теги при поиске без фильтров
@ads_router.callback_query(F.data.startswith(("tag:", "only_new", "skip")), StateFilter(AdsViewForm.select_tags))
async def process_tag_filter(call: types.CallbackQuery, state: FSMContext):
    telegram_id = str(call.from_user.id)
    logger.debug(f"process_tag_filter: Начало обработки для telegram_id={telegram_id}, callback_data={call.data}")
    data = await state.get_data()
    logger.debug(f"process_tag_filter: telegram_id={telegram_id}, state_data={data}")
    category = data.get("category")
    city = data.get("city")
    tags = data.get("tags", [])
    only_new = data.get("only_new", False)
    tags_selected = data.get("tags_selected", False)  # Флаг выбора тегов в текущем поиске

    callback_data = call.data

    # Если теги не выбраны в текущем поиске, сбрасываем их
    if not tags_selected and callback_data != "tag:":
        tags = []
        await state.update_data(tags=tags, tags_selected=False)

    if callback_data.startswith("tag:"):
        tag_id = int(callback_data.split(":")[1])
        async for session in get_db():
            result = await session.execute(select(Tag).where(Tag.id == tag_id))
            tag = result.scalar_one_or_none()
            if tag and tag.name not in tags:
                tags.append(tag.name)
                await state.update_data(tags=tags, tags_selected=True)  # Устанавливаем флаг при выборе тега
                await call.answer(f"Выбран тег: {tag.name}")
        tags_list = await get_category_tags(category, city)
        buttons = [tags_list[i:i + 3] for i in range(0, len(tags_list), 3)]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"tag:{id}") for id, name in row] for row in buttons
        ])
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="Только новые" if not only_new else "Все объявления", callback_data="only_new"),
            InlineKeyboardButton(text="Найти", callback_data="skip")
        ])
        selected_filters = tags.copy()
        if only_new:
            selected_filters.append("Только новые")
        await call.message.edit_text(
            f"Выберите теги для фильтрации в {city} (выбрано: {', '.join(selected_filters) if selected_filters else 'ничего'}, или нажмите Найти для поиска):",
            reply_markup=keyboard
        )
        return

    elif callback_data == "only_new":
        only_new = not only_new
        await state.update_data(only_new=only_new)
        tags_list = await get_category_tags(category, city)
        buttons = [tags_list[i:i + 3] for i in range(0, len(tags_list), 3)]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"tag:{id}") for id, name in row] for row in buttons
        ])
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="Только новые" if not only_new else "Все объявления", callback_data="only_new"),
            InlineKeyboardButton(text="Найти", callback_data="skip")
        ])
        selected_filters = tags.copy()
        if only_new:
            selected_filters.append("Только новые")
        await call.message.edit_text(
            f"Выберите теги для фильтрации в {city} (выбрано: {', '.join(selected_filters) if selected_filters else 'ничего'}, или нажмите Найти для поиска):",
            reply_markup=keyboard
        )
        await call.answer(f"Фильтр 'Только новые': {'вкл' if only_new else 'выкл'}")
        return

    elif callback_data == "skip":
        logger.debug(f"process_tag_filter: telegram_id={telegram_id}, начало блока skip")
        async for session in get_db():
            logger.debug(f"process_tag_filter: telegram_id={telegram_id}, перед запросом к базе")
            result = await session.execute(select(User.id).where(User.telegram_id == telegram_id))
            user_id = result.scalar_one_or_none()
            if not user_id:
                await call.message.edit_text(
                    "Ошибка: пользователь не найден.\n:", reply_markup=get_main_menu_keyboard()
                )
                await state.clear()
                await call.answer()
                return

            query = select(Advertisement).where(
                Advertisement.category == category,
                Advertisement.city == city,
                Advertisement.status == "approved"
            )
            if tags and tags_selected:  # Применяем теги только если они выбраны в текущем поиске
                query = query.where(Advertisement.tags.contains(tags))
            if only_new:
                query = query.where(~Advertisement.id.in_(
                    select(ViewedAds.advertisement_id).where(ViewedAds.user_id == user_id)
                ))
            ads = await session.execute(query.order_by(Advertisement.id))
            ads = ads.scalars().all()
            logger.debug(f"process_tag_filter: telegram_id={telegram_id}, найдено объявлений: {len(ads)}, IDs: {[ad.id for ad in ads]}")

            if not ads:
                await state.update_data(tags=[], only_new=False, tags_selected=False)  # Очищаем теги при отсутствии результатов
                tags_list = await get_category_tags(category, city)
                buttons = [tags_list[i:i + 3] for i in range(0, len(tags_list), 3)]
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=name, callback_data=f"tag:{id}") for id, name in row] for row in buttons
                ])
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton(text="Только новые", callback_data="only_new"),
                    InlineKeyboardButton(text="Найти", callback_data="skip")
                ])
                await call.message.edit_text(
                    f"Объявлений в {city} по вашим фильтрам не найдено. Попробуйте другие фильтры:",
                    reply_markup=keyboard
                )
                await call.answer()
                return

            logger.debug(f"process_tag_filter: telegram_id={telegram_id}, начало отправки объявлений")
            await call.message.delete()
            await call.message.bot.send_message(
                chat_id=call.from_user.id,
                text=f"Найдено {len(ads)} объявлений\n" + "―" * 27
            )
            for ad in ads:
                buttons = [[InlineKeyboardButton(
                    text="В избранное",
                    callback_data=f"favorite:add:{ad.id}"
                )]]
                logger.debug(f"Отправка объявления ID {ad.id} для telegram_id={telegram_id}")
                await render_ad(ad, call.message.bot, call.from_user.id, show_status=False, buttons=buttons)

            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Помощь", callback_data="action:help"),
                InlineKeyboardButton(text="Добавить своё", callback_data="action:add"),
                InlineKeyboardButton(text="Назад", callback_data="action:back")
            ]])
            await state.update_data(category=category, tags_selected=False)  # Сбрасываем флаг после вывода
            await call.message.bot.send_message(
                chat_id=call.from_user.id,
                text="Режим просмотра объявлений",
                reply_markup=keyboard
            )
            logger.debug(f"Отправлено финальное меню")
            await call.answer()