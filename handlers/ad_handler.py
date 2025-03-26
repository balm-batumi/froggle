from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram import F
from states import AdAddForm
from database import get_db, User, Tag, City, Advertisement, add_advertisement, get_category_tags, get_cities, get_all_category_tags, select  # Добавлен get_all_category_tags
from data.constants import get_main_menu_keyboard
from data.categories import CATEGORIES
from loguru import logger
import asyncio

ad_router = Router()

# Начало процесса добавления
@ad_router.message(F.text == "Добавить своё")
async def process_ad_start(message: types.Message, state: FSMContext):
    logger.info(f"process_ad_start вызвана для telegram_id={message.from_user.id}")
    data = await state.get_data()
    category = data.get("category")
    if not category or category not in CATEGORIES:
        logger.info(f"Категория не выбрана или неверна: {category}")
        await message.answer("Пожалуйста, выберите категорию из главного меню.\n:", reply_markup=get_main_menu_keyboard())
        return

    logger.info(f"Начало добавления объявления в категории {category} для telegram_id={message.from_user.id}")
    await state.set_state(AdAddForm.city)
    await state.update_data(category=category)
    logger.info(f"Отправка меню городов для категории {category}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Тбилиси", callback_data=f"city:{category}:Тбилиси"),
         InlineKeyboardButton(text="Батуми", callback_data=f"city:{category}:Батуми")],
        [InlineKeyboardButton(text="Кутаиси", callback_data=f"city:{category}:Кутаиси"),
         InlineKeyboardButton(text="Гори", callback_data=f"city:{category}:Гори")],
        [InlineKeyboardButton(text="Другой город", callback_data=f"city_other:{category}"),
         InlineKeyboardButton(text="Помощь", callback_data=f"help:{category}:city"),
         InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    await message.answer(
        CATEGORIES[category]["texts"]["city"],
        reply_markup=keyboard
    )


# Обработчик callback’а action:add для начала добавления объявления с текущей категорией
@ad_router.callback_query(F.data == "action:add")
async def process_ad_start_from_callback(call: types.CallbackQuery, state: FSMContext):
    logger.info(f"process_ad_start_from_callback вызвана для telegram_id={call.from_user.id}")
    data = await state.get_data()
    category = data.get("category")
    if not category or category not in CATEGORIES:
        logger.info(f"Категория не выбрана или неверна: {category}")
        await call.message.edit_text(
            "Пожалуйста, выберите категорию из главного меню.\n:",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        await call.answer()
        return

    logger.info(f"Начало добавления объявления в категории {category} для telegram_id={call.from_user.id}")
    await state.set_state(AdAddForm.city)
    await state.update_data(category=category)
    logger.info(f"Отправка меню городов для категории {category}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Тбилиси", callback_data=f"city:{category}:Тбилиси"),
         InlineKeyboardButton(text="Батуми", callback_data=f"city:{category}:Батуми")],
        [InlineKeyboardButton(text="Кутаиси", callback_data=f"city:{category}:Кутаиси"),
         InlineKeyboardButton(text="Гори", callback_data=f"city:{category}:Гори")],
        [InlineKeyboardButton(text="Другой город", callback_data=f"city_other:{category}"),
         InlineKeyboardButton(text="Помощь", callback_data=f"help:{category}:city"),
         InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    await call.message.edit_text(
        CATEGORIES[category]["texts"]["city"],
        reply_markup=keyboard
    )
    await call.answer()


# Обработчик выбора города для перехода к выбору всех тегов категории
@ad_router.callback_query(F.data.startswith("city:"), StateFilter(AdAddForm.city))
async def process_city_selection(call: types.CallbackQuery, state: FSMContext):
    _, category, city = call.data.split(":", 2)
    data = await state.get_data()
    logger.info(f"Выбран город '{city}' для telegram_id={call.from_user.id} в категории {category}")
    await state.update_data(city=city)
    tags = await get_all_category_tags(category)  # Используем все теги категории
    if not tags:
        await call.message.edit_text(
            "Нет доступных тегов. Обратитесь к администратору.\n:", reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        return
    buttons = [tags[i:i + 3] for i in range(0, len(tags), 3)]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"tag_select:{id}") for id, name in row] for row in buttons
    ])
    await call.message.edit_text(
        CATEGORIES[category]["texts"]["tags"],
        reply_markup=keyboard
    )
    await call.answer()
    await state.set_state(AdAddForm.tags)


# Обрабатывает выбор "Другой город" и отображает список доступных городов
@ad_router.callback_query(F.data.startswith("city_other:"), StateFilter(AdAddForm.city))
async def process_city_other(call: types.CallbackQuery, state: FSMContext):
    category = call.data.split(":", 1)[1]
    logger.info(f"Пользователь {call.from_user.id} выбрал 'Другой город' для категории '{category}'")

    cities = await get_cities()
    main_cities = ["Тбилиси", "Батуми", "Кутаиси", "Гори"]
    other_cities = [city for city in cities.keys() if city not in main_cities]
    buttons = [
        InlineKeyboardButton(text=city, callback_data=f"city:{category}:{city}")
        for city in other_cities
    ]
    keyboard_rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await call.message.edit_text(
        "Выберите другой город:",
        reply_markup=keyboard
    )
    await call.answer()

# Обработчик выбора тега для добавления в список с отображением всех тегов категории
@ad_router.callback_query(F.data.startswith("tag_select:"), StateFilter(AdAddForm.tags))
async def process_ad_tags(call: types.CallbackQuery, state: FSMContext):
    tag_id = int(call.data.split(":", 1)[1])
    data = await state.get_data()
    category = data.get("category")
    tags = data.get("tags", [])  # Список уже выбранных тегов
    previous_tags = tags.copy()  # Сохраняем предыдущее состояние

    if len(tags) >= 3:
        await call.answer("У вас уже выбрано 3 тега", show_alert=True)
        return

    async for session in get_db():
        result = await session.execute(select(Tag).where(Tag.id == tag_id))
        tag = result.scalar_one_or_none()
        if tag and tag.name not in tags:  # Добавляем только новый тег
            tags.append(tag.name)
            await state.update_data(tags=tags)

        if tags == previous_tags:  # Если ничего не изменилось
            await call.answer()
            return

        tags_list = await get_all_category_tags(category)  # Используем все теги категории
        buttons = [tags_list[i:i + 3] for i in range(0, len(tags_list), 3)]
        keyboard_rows = [
            [InlineKeyboardButton(text=name, callback_data=f"tag_select:{id}") for id, name in row] for row in buttons
        ]

        # Проверяем наличие primary_tag
        primary_tags = [tag.name for tag in (await session.execute(select(Tag).where(Tag.is_primary == True))).scalars().all()]
        has_primary = any(tag_name in primary_tags for tag_name in tags)
        if has_primary:
            keyboard_rows.append([InlineKeyboardButton(text="Далее", callback_data="next_to_title")])
            await call.message.edit_text(
                f"Выбрано: {', '.join(tags)}\nНажмите 'Далее' для продолжения.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
            )
        else:
            await call.message.edit_text(
                f"Выбрано: {', '.join(tags)}\nВыберите хотя бы один обязательный тег.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
            )
        await call.answer()


# Обработчик кнопки "Далее" для перехода к вводу названия
@ad_router.callback_query(F.data == "next_to_title", StateFilter(AdAddForm.tags))
async def process_next_to_title(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    category = data.get("category")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Помощь", callback_data=f"help:{category}:title"),
         InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    await call.message.edit_text(
        CATEGORIES[category]["texts"]["title"],
        reply_markup=keyboard
    )
    await state.set_state(AdAddForm.title)
    await call.answer()


# Ввод заголовка
@ad_router.message(StateFilter(AdAddForm.title))
async def process_ad_title(message: types.Message, state: FSMContext):
    title = message.text.strip()
    data = await state.get_data()
    category = data.get("category")
    await state.update_data(title=title)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Помощь", callback_data=f"help:{category}:description"),
         InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    await message.answer(
        CATEGORIES[category]["texts"]["description"],
        reply_markup=keyboard
    )
    await state.set_state(AdAddForm.description)

# Ввод описания
@ad_router.message(StateFilter(AdAddForm.description))
async def process_ad_description(message: types.Message, state: FSMContext):
    description = message.text.strip()
    data = await state.get_data()
    category = data.get("category")
    await state.update_data(description=description)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Без цены", callback_data="skip_price")],
        [InlineKeyboardButton(text="Помощь", callback_data=f"help:{category}:price"),
         InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    await message.answer(
        CATEGORIES[category]["texts"]["price"],
        reply_markup=keyboard
    )
    await state.set_state(AdAddForm.price)

# Ввод цены
@ad_router.message(StateFilter(AdAddForm.price))
async def process_ad_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data.get("category")
    price = message.text.strip()[:30]  # Обрезаем до 30 символов
    await state.update_data(price=price)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить загрузку медиа", callback_data="media_skip")],
        [InlineKeyboardButton(text="Помощь", callback_data=f"help:{category}:media"),
         InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    await message.answer(
        CATEGORIES[category]["texts"]["media"],
        reply_markup=keyboard
    )
    await state.set_state(AdAddForm.media)

# Пропуск цены
@ad_router.callback_query(F.data == "skip_price", StateFilter(AdAddForm.price))
async def process_ad_price_skip(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(price=None)
    data = await state.get_data()
    category = data.get("category")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить загрузку медиа", callback_data="media_skip")],
        [InlineKeyboardButton(text="Помощь", callback_data=f"help:{category}:media"),
         InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    await call.message.edit_text(
        CATEGORIES[category]["texts"]["media"],
        reply_markup=keyboard
    )
    await state.set_state(AdAddForm.media)
    await call.answer()


# Обрабатывает загрузку медиа и сохраняет их с типом в формате JSONB
@ad_router.message(F.photo | F.video, StateFilter(AdAddForm.media))
async def process_ad_media(message: types.Message, state: FSMContext):
    if message.from_user.is_bot:
        logger.debug(f"Сообщение от бота {message.from_user.id} проигнорировано")
        return

    # Определяем тип медиа и file_id
    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
    else:
        logger.debug(f"Нет file_id в сообщении от {message.from_user.id}")
        return

    media_group_id = message.media_group_id
    data = await state.get_data()
    category = data.get("category")
    media_file_ids = data.get("media_file_ids", []) or []  # Убеждаемся, что это список
    media_message_id = data.get("media_message_id")
    media_groups = data.get("media_groups", {})
    last_group_time = data.get("last_group_time", 0)
    current_time = asyncio.get_event_loop().time()
    logger.debug(f"Начало обработки медиа: file_id={file_id}, media_group_id={media_group_id}, текущие файлы={media_file_ids}")

    # Проверяем, добавлен ли этот file_id ранее
    if not any(media["id"] == file_id for media in media_file_ids):
        media_file_ids.append({"id": file_id, "type": media_type})
        if media_group_id:
            # Накопление файлов группы
            group_files = media_groups.get(media_group_id, [])
            group_files.append({"id": file_id, "type": media_type})
            media_groups[media_group_id] = group_files
            await state.update_data(media_file_ids=media_file_ids[:10], media_groups=media_groups, last_group_time=current_time)
            logger.debug(f"Добавлен файл в группу: {media_group_id}, files={group_files}")

            # Ждем 1 секунду после последнего файла группы
            await asyncio.sleep(1)
            data = await state.get_data()
            if data.get("last_group_time") == current_time:  # Это последний файл группы
                file_count = len(data.get("media_file_ids", []))
                text = f"Загружено {file_count} файлов" if file_count > 1 else f"Загружено {file_count} файл"
                try:
                    if not media_message_id:
                        msg = await message.answer(text)
                        await state.update_data(media_message_id=msg.message_id)
                        logger.debug(f"Создано сообщение: message_id={msg.message_id}, text='{text}'")
                    else:
                        await message.bot.edit_message_text(
                            text=text,
                            chat_id=message.chat.id,
                            message_id=media_message_id
                        )
                        logger.debug(f"Отредактировано сообщение: message_id={media_message_id}, text='{text}'")
                except Exception as e:
                    logger.error(f"Ошибка при обработке медиа-группы для telegram_id={message.from_user.id}: {e}")
                    await message.answer("Ошибка при загрузке файлов. Попробуйте снова.")
                await state.set_state(AdAddForm.contacts)
                await _send_contact_options(message, state)
        else:
            # Одиночный файл
            file_count = len(media_file_ids)
            text = f"Загружено {file_count} файлов" if file_count > 1 else f"Загружено {file_count} файл"
            await state.update_data(media_file_ids=media_file_ids[:10])
            logger.debug(f"Сохранён одиночный файл: media_file_ids={media_file_ids}")
            try:
                if not media_message_id:
                    msg = await message.answer(text)
                    await state.update_data(media_message_id=msg.message_id)
                    logger.debug(f"Создано сообщение для одиночного файла: message_id={msg.message_id}, text='{text}'")
                else:
                    await message.bot.edit_message_text(
                        text=text,
                        chat_id=message.chat.id,
                        message_id=media_message_id
                    )
                    logger.debug(f"Отредактировано сообщение для одиночного файла: message_id={media_message_id}, text='{text}'")
            except Exception as e:
                logger.error(f"Ошибка при обработке одиночного медиа для telegram_id={message.from_user.id}: {e}")
                await message.answer("Ошибка при загрузке файла. Попробуйте снова.")
            logger.debug(f"Переход к состоянию AdAddForm.contacts для telegram_id={message.from_user.id}")
            await state.set_state(AdAddForm.contacts)
            logger.debug(f"Состояние изменено, вызов _send_contact_options для telegram_id={message.from_user.id}")
            await _send_contact_options(message, state)

# Пропуск загрузки медиа
@ad_router.callback_query(F.data == "media_skip", StateFilter(AdAddForm.media))
async def process_ad_skip(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(media_file_ids=[])
    logger.info(f"Пользователь {call.from_user.id} пропустил загрузку медиа")
    if call.from_user.is_bot:
        logger.debug(f"Пользователь {call.from_user.id} — бот, дальнейшие действия невозможны")
        await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text="Боты не могут добавлять объявления.\n:", reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
    else:
        logger.debug(f"Переход к выбору контактов для пользователя {call.from_user.id}")
        await state.set_state(AdAddForm.contacts)
        await _send_contact_options(call, state)
    await call.answer()

# Отправляет варианты выбора контактов для объявления
async def _send_contact_options(message_or_call, state: FSMContext):
    if isinstance(message_or_call, types.Message):
        telegram_id = str(message_or_call.from_user.id)
        username = message_or_call.from_user.username
        is_bot = message_or_call.from_user.is_bot
        chat_id = message_or_call.from_user.id
        bot = message_or_call.bot
    else:  # isinstance(message_or_call, types.CallbackQuery)
        telegram_id = str(message_or_call.from_user.id)
        username = message_or_call.from_user.username
        is_bot = message_or_call.from_user.is_bot
        chat_id = message_or_call.from_user.id
        bot = message_or_call.message.bot

    data = await state.get_data()
    if is_bot:
        logger.debug(f"Сообщение от бота {telegram_id} проигнорировано")
        return

    logger.debug(f"Получение сохранённых контактов для {telegram_id}")
    async for session in get_db():
        result = await session.execute(
            select(Advertisement.contact_info)
            .where(Advertisement.user_id == select(User.id).where(User.telegram_id == telegram_id).scalar_subquery())
            .order_by(Advertisement.created_at.desc())
            .limit(1)
        )
        saved_contact = result.scalar_one_or_none()
        logger.debug(f"Сохранённый контакт для {telegram_id}: {saved_contact}")

    buttons = []
    if username:
        buttons.append([InlineKeyboardButton(text=f"ввести юзернейм: @{username}", callback_data="contact:username")])
    if saved_contact:
        buttons.append([InlineKeyboardButton(text=f"контакт из БД: {saved_contact}", callback_data="contact:saved")])
    if not username and not saved_contact:
        buttons.append([InlineKeyboardButton(text="Ввести вручную", callback_data="contact:manual")])
    buttons.append([InlineKeyboardButton(text="Помощь", callback_data=f"help:{data.get('category', 'unknown')}:contacts"),
                    InlineKeyboardButton(text="Назад", callback_data="back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    logger.debug(f"Отправка сообщения с контактами для {telegram_id}")
    await bot.send_message(
        chat_id=chat_id,
        text=CATEGORIES[data.get('category', 'unknown')]["texts"]["contacts"],
        reply_markup=keyboard
    )

# Выбор контактов через инлайн-кнопки
@ad_router.callback_query(F.data.startswith("contact:"), StateFilter(AdAddForm.contacts))
async def process_contact_choice(call: types.CallbackQuery, state: FSMContext):
    action = call.data.split(":", 1)[1]
    username = call.from_user.username
    telegram_id = str(call.from_user.id)
    data = await state.get_data()

    async for session in get_db():
        result = await session.execute(
            select(Advertisement.contact_info)
            .where(Advertisement.user_id == select(User.id).where(User.telegram_id == str(telegram_id)).scalar_subquery())
            .order_by(Advertisement.created_at.desc())
            .limit(1)
        )
        saved_contact = result.scalar_one_or_none()

    if action == "username" and username:
        contact_text = f"@{username}"
    elif action == "saved" and saved_contact:
        contact_text = saved_contact
    else:
        await call.answer("Ошибка выбора контакта.", show_alert=True)
        return

    await state.update_data(selected_contact=contact_text)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить", callback_data="confirm_contact")],
        [InlineKeyboardButton(text="Помощь", callback_data=f"help:{data.get('category', 'unknown')}:contacts"),
         InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    await call.message.edit_text(
        f"Ваши контакты будут выглядеть так: <code>{contact_text}</code>\nВведите дополнительные данные или подтвердите:",
        reply_markup=keyboard
    )
    await call.answer()

# Подтверждение контактов
@ad_router.callback_query(F.data == "confirm_contact", StateFilter(AdAddForm.contacts))
async def process_confirm_contact(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_contact = data.get("selected_contact", "")
    if not selected_contact:
        await call.message.edit_text("Ошибка: контакт не выбран. Попробуйте снова.\n:", reply_markup=get_main_menu_keyboard())
        await state.clear()
        return
    await state.update_data(contacts=selected_contact)
    preview = (
        f"Категория: {data.get('category', 'не указана')}\n"
        f"Город: {data['city']}\n"
        f"Теги: {', '.join(data['tags']) if data['tags'] else 'нет'}\n"
        f"Заголовок: {data['title']}\n"
        f"Описание: {data['description']}\n"
        f"Цена: {data.get('price', 'без цены')}\n"
        f"Медиа: {'Есть' if data.get('media_file_ids') else 'Нет'}\n"
        f"Контакты: {selected_contact}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сохранить", callback_data="confirm:save"),
         InlineKeyboardButton(text="Отменить", callback_data="confirm:cancel")]
    ])
    await call.message.edit_text(preview, reply_markup=keyboard)
    await state.set_state(AdAddForm.confirm)
    await call.answer()

# Ручной ввод контактов
@ad_router.message(StateFilter(AdAddForm.contacts))
async def process_ad_contacts_manual(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data.get("category")
    selected_contact = data.get("selected_contact", "")
    additional_text = message.text.strip()
    contacts = f"{selected_contact} {additional_text}" if selected_contact and additional_text else selected_contact or additional_text
    if not contacts:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Помощь", callback_data=f"help:{category}:contacts"),
             InlineKeyboardButton(text="Назад", callback_data="back")]
        ])
        await message.answer("Контакты не могут быть пустыми. Введите данные:", reply_markup=keyboard)
        return
    await state.update_data(contacts=contacts)
    preview = (
        f"Категория: {category}\n"
        f"Город: {data['city']}\n"
        f"Теги: {', '.join(data['tags']) if data['tags'] else 'нет'}\n"
        f"Заголовок: {data['title']}\n"
        f"Описание: {data['description']}\n"
        f"Цена: {data.get('price', 'без цены')}\n"
        f"Медиа: {'Есть' if data.get('media_file_ids') else 'Нет'}\n"
        f"Контакты: {contacts}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сохранить", callback_data="confirm:save"),
         InlineKeyboardButton(text="Отменить", callback_data="confirm:cancel")]
    ])
    await message.answer(preview, reply_markup=keyboard)
    await state.set_state(AdAddForm.confirm)

# Подтверждение объявления
@ad_router.callback_query(F.data.startswith("confirm:"), StateFilter(AdAddForm.confirm))
async def process_ad_confirm(call: types.CallbackQuery, state: FSMContext):
    action = call.data.split(":", 1)[1]
    data = await state.get_data()
    telegram_id = str(call.from_user.id)

    if action == "save":
        async for session in get_db():
            stmt = select(User.id).where(User.telegram_id == telegram_id)
            result = await session.execute(stmt)
            user_id = result.scalar_one_or_none()
            if not user_id:
                await call.message.edit_text("Пользователь не найден. Используйте /start.\n:", reply_markup=get_main_menu_keyboard())
                await state.clear()
                return
            ad_id = await add_advertisement(
                user_id=user_id,
                category=data["category"],
                city=data["city"],
                title_ru=data["title"],
                description_ru=data["description"],
                tags=data.get("tags", []),
                media_file_ids=data.get("media_file_ids"),
                contact_info=data["contacts"],
                price=data.get("price")
            )
            logger.info(f"Объявление #{ad_id} добавлено для telegram_id={telegram_id}")
        await call.message.edit_text(
            f"Объявление сохранено и отправлено на модерацию\n:", reply_markup=get_main_menu_keyboard()
        )
    elif action == "cancel":
        await call.message.edit_text(
            f"Добавление объявления отменено\n:", reply_markup=get_main_menu_keyboard()
        )
    await state.clear()
    await call.answer()

# Обработчик "Назад"
@ad_router.callback_query(F.data == "back", StateFilter(AdAddForm))
async def process_ad_back(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Возврат в главное меню.\n:", reply_markup=get_main_menu_keyboard())
    await state.clear()
    await call.answer()

# Обработчик "Помощь"
@ad_router.callback_query(F.data.startswith("help:"), StateFilter(AdAddForm))
async def process_ad_help(call: types.CallbackQuery, state: FSMContext):
    _, category, step = call.data.split(":", 2)
    data = await state.get_data()
    category = data.get("category", category)
    help_text = CATEGORIES[category]["texts"].get(f"help_{step}", "Помощь для этого шага недоступна.")
    await call.message.bot.send_message(
        chat_id=call.from_user.id,
        text=help_text
    )
    await call.answer()