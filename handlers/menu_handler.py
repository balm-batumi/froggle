from aiogram import Router, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from states import MenuState, AdAddForm
from database import get_db, User, select, Favorite, Advertisement, remove_from_favorites, add_to_favorites, Subscription, get_cities, get_all_category_tags, Tag
from data.constants import get_main_menu_keyboard
from data.categories import CATEGORIES
from tools.utils import render_ad
from loguru import logger
from states import AdsViewForm, SubscribeForm

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

# Обработчик команды /start для показа главного меню
@menu_router.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
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

    await state.set_state(AdsViewForm.select_category)
    logger.debug(f"Отправляем главное меню с клавиатурой: {get_main_menu_keyboard().__class__.__name__}")
    await message.answer(
        "Добро пожаловать в Froggle! Выберите категорию:",
        reply_markup=get_main_menu_keyboard()
    )

@menu_router.callback_query(F.data == "action:help")
async def help_handler(call: types.CallbackQuery):
    await call.message.edit_text(
        "Froggle — ваш помощник. Выберите категорию для просмотра объявлений.",
        reply_markup=get_main_menu_keyboard()
    )
    await call.answer()

# Обработчик команды "Настройки" для отображения меню настроек
@menu_router.callback_query(F.data == "action:settings")
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
                [InlineKeyboardButton(text="📩 Подписки", callback_data="action:subscriptions")],
                [InlineKeyboardButton(text="⬅️", callback_data="action:back")]
            ])
            await call.message.edit_text("Настройки для админа:", reply_markup=keyboard)
        else:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Избранное", callback_data="show_favorites")],
                [InlineKeyboardButton(text="Мои", callback_data="show_my_ads")],
                [InlineKeyboardButton(text="📩 Подписки", callback_data="action:subscriptions")],
                [InlineKeyboardButton(text="⬅️", callback_data="action:back")]
            ])
            await call.message.edit_text("Ваши настройки:", reply_markup=keyboard)
    await call.answer()


# Обработчик для отображения и управления подписками
@menu_router.callback_query(F.data == "action:subscriptions")
async def subscriptions_handler(call: types.CallbackQuery, state: FSMContext):
    telegram_id = str(call.from_user.id)

    async for session in get_db():
        # Получаем пользователя
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()
        if not user:
            await call.message.edit_text("Пользователь не найден. Используйте /start.",
                                         reply_markup=get_main_menu_keyboard())
            return

        # Получаем подписки пользователя
        subscriptions_result = await session.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        subscriptions = subscriptions_result.scalars().all()

        if not subscriptions:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="➕ Добавить", callback_data="action:subscribe"),
                InlineKeyboardButton(text="❓", callback_data="help:subscriptions"),
                InlineKeyboardButton(text="⬅️", callback_data="action:settings")
            ]])
            await call.message.edit_text(
                "У вас нет подписок. Создайте первую подписку!",
                reply_markup=keyboard
            )
        else:
            # Удаляем предыдущее сообщение
            await call.message.delete()

            # Выводим каждую подписку как отдельное сообщение
            for sub in subscriptions:
                sub_text = (
                    f"Подписка #{sub.id}\n"
                    f"Город: {sub.city}\n"
                    f"Категория: {sub.category}\n"
                    f"Теги: {', '.join(sub.tags)}"
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_subscription:{sub.id}")
                ]])
                await call.message.bot.send_message(
                    chat_id=call.from_user.id,
                    text=sub_text,
                    reply_markup=keyboard
                )

            # Добавляем кнопку "Добавить" (неактивна, если есть подписка)
            add_button = InlineKeyboardButton(text="➕ Добавить (Пока🔒)",
                                              callback_data="disabled") if subscriptions else InlineKeyboardButton(
                text="➕ Добавить", callback_data="action:subscribe")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                add_button,
                InlineKeyboardButton(text="⬅️", callback_data="action:settings")
            ]])
            await call.message.bot.send_message(
                chat_id=call.from_user.id,
                text="Ваши подписки 👆",
                reply_markup=keyboard
            )

    await call.answer()


# Обработчик для неактивной кнопки "Пока недоступно"
@menu_router.callback_query(F.data == "disabled")
async def disabled_button_handler(call: types.CallbackQuery):
    await call.answer("Вам недоступно создание новых подписок.", show_alert=True)


# Обработчик начала создания подписки
@menu_router.callback_query(F.data == "action:subscribe")
async def subscribe_start_handler(call: types.CallbackQuery, state: FSMContext):
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await call.message.edit_text("Пользователь не найден. Используйте /start.", reply_markup=get_main_menu_keyboard())
            return

        # Получаем список городов из базы
        cities = await get_cities()
        main_cities = ["Тбилиси", "Батуми", "Кутаиси", "Гори"]  # Основные города для первого экрана
        buttons = [
            InlineKeyboardButton(text=city, callback_data=f"subscribe_city:{city}")
            for city in main_cities if city in cities
        ]
        keyboard_rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]  # По 2 кнопки в ряд
        keyboard_rows.append([
            InlineKeyboardButton(text="Другие города", callback_data="subscribe_city_other"),
            InlineKeyboardButton(text="❓", callback_data="help:subscribe_city"),
            InlineKeyboardButton(text="⬅️", callback_data="action:subscriptions")
        ])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await call.message.edit_text("Выберите город для подписки:", reply_markup=keyboard)
        await state.set_state("SubscribeForm:select_city")
        await call.answer()


# Добавьте этот импорт в начало файла, если его там ещё нет
from aiogram.filters import StateFilter


# Обработчик выбора "Другие города" для подписки
@menu_router.callback_query(F.data == "subscribe_city_other", StateFilter("SubscribeForm:select_city"))
async def subscribe_city_other_handler(call: types.CallbackQuery, state: FSMContext):
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await call.message.edit_text("Пользователь не найден. Используйте /start.",
                                         reply_markup=get_main_menu_keyboard())
            await state.clear()
            return

        # Получаем список городов из базы
        cities = await get_cities()
        main_cities = ["Тбилиси", "Батуми", "Кутаиси", "Гори"]  # Основные города, которые уже показаны
        other_cities = [city for city in cities.keys() if city not in main_cities]
        buttons = [
            InlineKeyboardButton(text=city, callback_data=f"subscribe_city:{city}")
            for city in other_cities
        ]
        keyboard_rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]  # По 3 кнопки в ряд
        keyboard_rows.append([
            InlineKeyboardButton(text="❓", callback_data="help:subscribe_city"),
            InlineKeyboardButton(text="⬅️", callback_data="action:subscriptions")
        ])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

        await call.message.edit_text("Выберите другой город для подписки:", reply_markup=keyboard)
        await call.answer()


# Обработчик выбора конкретного города для подписки
@menu_router.callback_query(F.data.startswith("subscribe_city:"), StateFilter("SubscribeForm:select_city"))
async def subscribe_city_select_handler(call: types.CallbackQuery, state: FSMContext):
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await call.message.edit_text("Пользователь не найден. Используйте /start.",
                                         reply_markup=get_main_menu_keyboard())
            await state.clear()
            return

    # Извлекаем выбранный город из callback_data
    city = call.data.split(":", 1)[1]
    await state.update_data(city=city)

    # Список категорий из CATEGORIES
    buttons = [
        InlineKeyboardButton(text=CATEGORIES[cat]["display_name"], callback_data=f"subscribe_category:{cat}")
        for cat in CATEGORIES
    ]
    keyboard_rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]  # По 3 кнопки в ряд
    keyboard_rows.append([
        InlineKeyboardButton(text="❓", callback_data="help:subscribe_category"),
        InlineKeyboardButton(text="⬅️", callback_data="action:subscriptions")
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await call.message.edit_text("Выберите категорию для подписки:", reply_markup=keyboard)
    await state.set_state(SubscribeForm.select_category)
    await call.answer()


# Обработчик выбора категории для подписки
@menu_router.callback_query(F.data.startswith("subscribe_category:"), StateFilter("SubscribeForm:select_category"))
async def subscribe_category_select_handler(call: types.CallbackQuery, state: FSMContext):
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await call.message.edit_text("Пользователь не найден. Используйте /start.",
                                         reply_markup=get_main_menu_keyboard())
            await state.clear()
            return

    # Извлекаем выбранную категорию из callback_data
    category = call.data.split(":", 1)[1]
    await state.update_data(category=category)

    # Получаем теги для категории
    tags = await get_all_category_tags(category)
    buttons = [
        InlineKeyboardButton(text=name, callback_data=f"subscribe_tag:{id}")
        for id, name in tags
    ]
    keyboard_rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]  # По 3 кнопки в ряд
    keyboard_rows.append([
        InlineKeyboardButton(text="❓", callback_data="help:subscribe_tags"),
        InlineKeyboardButton(text="⬅️", callback_data="action:subscriptions")
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await call.message.edit_text("Выберите до 3 тегов для подписки:", reply_markup=keyboard)
    await state.set_state(SubscribeForm.select_tags)
    await call.answer()


# Обработчик выбора тегов для подписки
@menu_router.callback_query(F.data.startswith("subscribe_tag:"), StateFilter("SubscribeForm:select_tags"))
async def subscribe_tag_select_handler(call: types.CallbackQuery, state: FSMContext):
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await call.message.edit_text("Пользователь не найден. Используйте /start.",
                                         reply_markup=get_main_menu_keyboard())
            await state.clear()
            return

    # Извлекаем ID тега из callback_data
    tag_id = int(call.data.split(":", 1)[1])
    data = await state.get_data()
    category = data.get("category")
    tags = data.get("tags", [])  # Список выбранных тегов

    if len(tags) >= 3:
        await call.answer("Вы выбрали максимум 3 тега", show_alert=True)
        return

    # Получаем информацию о теге
    async for session in get_db():
        result = await session.execute(select(Tag).where(Tag.id == tag_id))
        tag = result.scalar_one_or_none()
        if tag and tag.name not in tags:
            tags.append(tag.name)
            await state.update_data(tags=tags)

    # Получаем все теги для категории
    all_tags = await get_all_category_tags(category)
    buttons = [
        InlineKeyboardButton(text=name, callback_data=f"subscribe_tag:{id}")
        for id, name in all_tags
    ]
    keyboard_rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    if tags:  # Добавляем "Сохранить", если выбран хотя бы один тег
        keyboard_rows.append([InlineKeyboardButton(text="💾 Сохранить", callback_data="subscribe_confirm")])
    keyboard_rows.append([
        InlineKeyboardButton(text="❓", callback_data="help:subscribe_tags"),
        InlineKeyboardButton(text="⬅️", callback_data="action:subscriptions")
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await call.message.edit_text(
        f"Выбрано: {', '.join(tags) if tags else 'ничего'}\nВыберите до 3 тегов или сохраните:",
        reply_markup=keyboard
    )
    await call.answer()


# Обработчик подтверждения подписки
@menu_router.callback_query(F.data == "subscribe_confirm", StateFilter("SubscribeForm:select_tags"))
async def subscribe_confirm_handler(call: types.CallbackQuery, state: FSMContext):
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await call.message.edit_text("Пользователь не найден. Используйте /start.",
                                         reply_markup=get_main_menu_keyboard())
            await state.clear()
            return

    # Получаем данные из состояния
    data = await state.get_data()
    city = data.get("city")
    category = data.get("category")
    tags = data.get("tags", [])

    # Формируем текст подписки
    sub_text = (
        "Подписка:\n"
        f"Город: {city}\n"
        f"Категория: {CATEGORIES[category]['display_name']}\n"
        f"Теги: {', '.join(tags) if tags else 'не выбраны'}"
    )

    # Создаём клавиатуру
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💾 Сохранить", callback_data="save_subscription"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_subscription"),
        InlineKeyboardButton(text="❓", callback_data="help:subscribe_confirm")
    ]])

    await call.message.edit_text(sub_text, reply_markup=keyboard)
    await state.set_state(SubscribeForm.confirm)
    await call.answer()


# Обработчик сохранения подписки
@menu_router.callback_query(F.data == "save_subscription", StateFilter("SubscribeForm:confirm"))
async def save_subscription_handler(call: types.CallbackQuery, state: FSMContext):
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        # Проверяем пользователя
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()
        if not user:
            await call.message.edit_text("Пользователь не найден. Используйте /start.", reply_markup=get_main_menu_keyboard())
            await state.clear()
            return

        # Получаем данные из состояния
        data = await state.get_data()
        city = data.get("city")
        category = data.get("category")
        tags = data.get("tags", [])

        # Создаём подписку
        subscription = Subscription(
            user_id=user.id,
            city=city,
            category=category,
            tags=tags
        )
        session.add(subscription)
        await session.commit()

    # Показываем сообщение и возвращаем в меню подписок
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️", callback_data="action:subscriptions")
    ]])
    await call.message.edit_text("Подписка сохранена!", reply_markup=keyboard)
    await state.clear()
    await call.answer()


@menu_router.callback_query(F.data == "show_my_ads")
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
            buttons = [[InlineKeyboardButton(text="Удалить", callback_data=f"delete_ad:{ad.id}")]]
            await render_ad(ad, call.message.bot, call.from_user.id, show_status=True, buttons=buttons, mark_viewed=True)

        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Помощь", callback_data="action:help"),
            InlineKeyboardButton(text="Назад", callback_data="action:settings")
        ]])
        await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text="Просмотр своих объявлений",
            reply_markup=back_keyboard
        )




@menu_router.callback_query(F.data.startswith("delete_ad:"))
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

@menu_router.callback_query(F.data == "show_favorites")
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
                text="У вас нет избранных объявлений",
                reply_markup=get_main_menu_keyboard()
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
                buttons = [[InlineKeyboardButton(
                    text="Удалить из избранного",
                    callback_data=f"favorite:remove:{ad.id}"
                )]]
                await render_ad(ad, call.message.bot, call.from_user.id, show_status=True, buttons=buttons, mark_viewed=True)
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

@menu_router.callback_query(F.data.startswith("favorite:remove:"))
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


# Добавляет объявление в избранное пользователя
@menu_router.callback_query(F.data.startswith("favorite:add:"))
async def add_to_favorites_handler(call: types.CallbackQuery):
    telegram_id = str(call.from_user.id)
    ad_id = int(call.data.split(":", 2)[2])

    async for session in get_db():
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()
        if not user:
            await call.answer("Пользователь не найден.", show_alert=True)
            return

        favorite_id = await add_to_favorites(user.id, ad_id)
        logger.info(f"Пользователь {telegram_id} добавил объявление #{ad_id} в избранное, favorite_id={favorite_id}")
        await call.answer("Добавлено в избранное!", show_alert=True)


@menu_router.callback_query(F.data == "action:back")
async def back_handler(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdsViewForm.select_category)
    await call.message.edit_text(  # Изменено на edit_text для консистентности
        "Возврат в главное меню",
        reply_markup=get_main_menu_keyboard()
    )
    await call.answer()