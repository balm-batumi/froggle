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


# Обработчик выбора категории для показа городов с дополнительными кнопками
@ads_router.callback_query(F.data.startswith("category:"), StateFilter(AdsViewForm.select_category))
async def show_cities_by_category(call: types.CallbackQuery, state: FSMContext):
    logger.debug(f"Хэндлер show_cities_by_category вызван: data={call.data}, state={await state.get_state()}")
    category = call.data.split(":", 1)[1]
    telegram_id = str(call.from_user.id)
    logger.info(f"Пользователь {telegram_id} выбрал категорию '{category}' для просмотра объявлений")
    cities = await get_cities(category)
    if not cities:
        display_name = CATEGORIES[category]["display_name"]
        await call.message.edit_text(
            f"В категории '{display_name}' нет одобренных объявлений.\n:",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        await call.answer()
        return

    # Формируем список городов с их количеством
    city_list = [(city, count) for city, count in cities.items()]
    # Группируем кнопки по 3 в строке
    buttons = [city_list[i:i + 3] for i in range(0, len(city_list), 3)]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{city} ({count})",
            callback_data=f"city_select:{category}:{city}"
        ) for city, count in row] for row in buttons
    ] + [[  # Добавляем нижнюю строку с тремя кнопками
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
@ads_router.callback_query(F.data.startswith("city_select:"), StateFilter(AdsViewForm.select_city))
async def show_ads_by_city(call: types.CallbackQuery, state: FSMContext):
    _, category, city = call.data.split(":", 2)
    telegram_id = str(call.from_user.id)
    logger.info(f"Пользователь {telegram_id} выбрал город '{city}' в категории '{category}'")

    await state.update_data(category=category, city=city)
    tags = await get_category_tags(category, city)
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
        InlineKeyboardButton(text="Пропустить", callback_data="skip")
    ])
    await call.message.edit_text(
        f"Выберите теги для фильтрации в {city}:",
        reply_markup=keyboard
    )
    await state.set_state(AdsViewForm.select_tags)
    await call.answer()


# Обрабатывает выбор тегов и выводит отфильтрованные объявления
@ads_router.callback_query(F.data.startswith(("tag:", "only_new", "skip")), StateFilter(AdsViewForm.select_tags))
async def process_tag_filter(call: types.CallbackQuery, state: FSMContext):
    telegram_id = str(call.from_user.id)
    data = await state.get_data()
    category = data.get("category")
    city = data.get("city")
    tags = data.get("tags", [])
    only_new = data.get("only_new", False)

    callback_data = call.data
    if callback_data.startswith("tag:"):
        tag_id = int(callback_data.split(":")[1])
        async for session in get_db():
            result = await session.execute(select(Tag).where(Tag.id == tag_id))
            tag = result.scalar_one_or_none()
            if tag and tag.name not in tags:
                tags.append(tag.name)
                await state.update_data(tags=tags)
                await call.answer(f"Выбран тег: {tag.name}")
        tags_list = await get_category_tags(category, city)
        buttons = [tags_list[i:i + 3] for i in range(0, len(tags_list), 3)]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"tag:{id}") for id, name in row] for row in buttons
        ])
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="Только новые" if not only_new else "Все объявления", callback_data="only_new"),
            InlineKeyboardButton(text="Пропустить", callback_data="skip")
        ])
        await call.message.edit_text(
            f"Выберите теги для фильтрации в {city} (выбрано: {', '.join(tags) if tags else 'ничего'}):",
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
            InlineKeyboardButton(text="Пропустить", callback_data="skip")
        ])
        await call.message.edit_text(
            f"Выберите теги для фильтрации в {city} (выбрано: {', '.join(tags) if tags else 'ничего'}):",
            reply_markup=keyboard
        )
        await call.answer(f"Фильтр 'Только новые': {'вкл' if only_new else 'выкл'}")
        return

    elif callback_data == "skip":
        async for session in get_db():
            # Получаем user_id по telegram_id
            result = await session.execute(select(User.id).where(User.telegram_id == telegram_id))
            user_id = result.scalar_one_or_none()
            if not user_id:
                await call.message.edit_text(
                    "Ошибка: пользователь не найден.\n:",
                    reply_markup=get_main_menu_keyboard()
                )
                await state.clear()
                await call.answer()
                return

            query = select(Advertisement).where(
                Advertisement.category == category,
                Advertisement.city == city,
                Advertisement.status == "approved"
            )
            if tags:
                query = query.where(Advertisement.tags.contains(tags))
            if only_new:
                query = query.where(~Advertisement.id.in_(
                    select(ViewedAds.advertisement_id).where(ViewedAds.user_id == user_id)
                ))
            ads = await session.execute(query.order_by(Advertisement.id))
            ads = ads.scalars().all()

            if not ads:
                await call.message.edit_text(
                    f"Объявлений в {city} по вашим фильтрам не найдено.\n:",
                    reply_markup=get_main_menu_keyboard()
                )
                await state.clear()
                await call.answer()
                return

            await call.message.delete()
            await call.message.bot.send_message(
                chat_id=call.from_user.id,
                text=f"Найдено {len(ads)} объявлений\n" + "―" * 27
            )
            for ad in ads:
                buttons = [InlineKeyboardButton(
                    text="В избранное",
                    callback_data=f"favorite:add:{ad.id}"
                )]
                await render_ad(ad, call.message.bot, call.from_user.id, show_status=False, buttons=buttons)

            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Помощь", callback_data="action:help"),
                InlineKeyboardButton(text="Добавить своё", callback_data="action:add"),
                InlineKeyboardButton(text="Назад", callback_data="action:back")
            ]])
            await call.message.bot.send_message(
                chat_id=call.from_user.id,
                text="Режим просмотра объявлений",
                reply_markup=keyboard
            )
            logger.debug(f"Отправлено финальное меню")
        await state.clear()
        await call.answer()