from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram import F
from states import AdAddForm
from database import get_db, User, Tag, City, Advertisement, add_advertisement, get_category_tags, get_cities, select
from data.constants import get_main_menu_keyboard
from loguru import logger
import asyncio

ad_router = Router()

# Хардкод категорий (временно, до переноса в data/categories.py)
AD_CATEGORIES = {
    "Услуги": {
        "tag_category": "Услуги",
        "multiple_tags": False,
        "texts": {
            "city": "Выберите город для услуги:",
            "tags": "Выберите сферу услуги:",
            "title": "Введите название услуги:",
            "description": "Введите описание услуги:",
            "media": "Отправьте фото или видео для услуги (до 10 файлов):",
            "contacts": "Укажите контактные данные для связи:",
            "help_city": "Выберите город из списка или введите свой.",
            "help_tags": "Выберите одну сферу из предложенных.",
            "help_title": "Введите краткое название (до 100 символов).",
            "help_description": "Опишите услугу подробно.",
            "help_media": "Загрузите до 10 фото/видео или пропустите.",
            "help_contacts": "Укажите телефон, Telegram или email."
        }
    },
    "Еда": {
        "tag_category": "Еда",
        "multiple_tags": False,
        "texts": {
            "city": "Выберите город для еды:",
            "tags": "Выберите категорию еды:",
            "title": "Введите название блюда или заведения:",
            "description": "Введите описание:",
            "media": "Отправьте фото или видео (до 10 файлов):",
            "contacts": "Укажите контактные данные:",
            "help_city": "Выберите город из списка или введите свой.",
            "help_tags": "Выберите одну категорию еды.",
            "help_title": "Введите краткое название (до 100 символов).",
            "help_description": "Опишите блюдо или заведение.",
            "help_media": "Загрузите до 10 фото/видео или пропустите.",
            "help_contacts": "Укажите телефон, Telegram или email."
        }
    },
    "Жильё": {
        "tag_category": "Жильё",
        "multiple_tags": False,
        "texts": {
            "city": "Выберите город для жилья:",
            "tags": "Выберите тип жилья:",
            "title": "Введите название жилья:",
            "description": "Введите описание жилья:",
            "media": "Отправьте фото или видео жилья (до 10 файлов):",
            "contacts": "Укажите контактные данные:",
            "help_city": "Выберите город из списка или введите свой.",
            "help_tags": "Выберите один тип жилья.",
            "help_title": "Введите краткое название (до 100 символов).",
            "help_description": "Опишите жильё подробно.",
            "help_media": "Загрузите до 10 фото/видео или пропустите.",
            "help_contacts": "Укажите телефон, Telegram или email."
        }
    },
    "Общение": {
        "tag_category": "Общение",
        "multiple_tags": False,
        "texts": {
            "city": "Выберите город для общения:",
            "tags": "Выберите цель общения:",
            "title": "Введите название:",
            "description": "Введите описание:",
            "media": "Отправьте фото или видео (до 10 файлов):",
            "contacts": "Укажите контактные данные:",
            "help_city": "Выберите город из списка или введите свой.",
            "help_tags": "Выберите одну цель общения.",
            "help_title": "Введите краткое название (до 100 символов).",
            "help_description": "Опишите цель общения.",
            "help_media": "Загрузите до 10 фото/видео или пропустите.",
            "help_contacts": "Укажите телефон, Telegram или email."
        }
    },
    "Авто": {
        "tag_category": "Авто",
        "multiple_tags": False,
        "texts": {
            "city": "Выберите город для авто:",
            "tags": "Выберите категорию авто:",
            "title": "Введите название:",
            "description": "Введите описание:",
            "media": "Отправьте фото или видео (до 10 файлов):",
            "contacts": "Укажите контактные данные:",
            "help_city": "Выберите город из списка или введите свой.",
            "help_tags": "Выберите одну категорию авто.",
            "help_title": "Введите краткое название (до 100 символов).",
            "help_description": "Опишите авто или услугу.",
            "help_media": "Загрузите до 10 фото/видео или пропустите.",
            "help_contacts": "Укажите телефон, Telegram или email."
        }
    },
    "Барахолка": {
        "tag_category": "Барахолка",
        "multiple_tags": False,
        "texts": {
            "city": "Выберите город для барахолки:",
            "tags": "Выберите категорию товара:",
            "title": "Введите название товара:",
            "description": "Введите описание товара:",
            "media": "Отправьте фото или видео (до 10 файлов):",
            "contacts": "Укажите контактные данные:",
            "help_city": "Выберите город из списка или введите свой.",
            "help_tags": "Выберите одну категорию товара.",
            "help_title": "Введите краткое название (до 100 символов).",
            "help_description": "Опишите товар подробно.",
            "help_media": "Загрузите до 10 фото/видео или пропустите.",
            "help_contacts": "Укажите телефон, Telegram или email."
        }
    },
    "Шоппинг": {
        "tag_category": "Шоппинг",
        "multiple_tags": False,
        "texts": {
            "city": "Выберите город для шоппинга:",
            "tags": "Выберите категорию шоппинга:",
            "title": "Введите название:",
            "description": "Введите описание:",
            "media": "Отправьте фото или видео (до 10 файлов):",
            "contacts": "Укажите контактные данные:",
            "help_city": "Выберите город из списка или введите свой.",
            "help_tags": "Выберите одну категорию шоппинга.",
            "help_title": "Введите краткое название (до 100 символов).",
            "help_description": "Опишите шоппинг или товар.",
            "help_media": "Загрузите до 10 фото/видео или пропустите.",
            "help_contacts": "Укажите телефон, Telegram или email."
        }
    }
}

# Начало процесса добавления
@ad_router.message(F.text == "Добавить своё")
async def process_ad_start(message: types.Message, state: FSMContext):
    logger.info(f"process_ad_start вызвана для telegram_id={message.from_user.id}")
    data = await state.get_data()
    category = data.get("category")
    if not category or category not in AD_CATEGORIES:
        logger.info(f"Категория не выбрана или неверна: {category}")
        await message.answer("Пожалуйста, выберите категорию из главного меню.\n🏠:", reply_markup=get_main_menu_keyboard())
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
        AD_CATEGORIES[category]["texts"]["city"],
        reply_markup=keyboard
    )

# Выбор города через инлайн-кнопки
@ad_router.callback_query(F.data.startswith("city:"), StateFilter(AdAddForm.city))
async def process_city_selection(call: types.CallbackQuery, state: FSMContext):
    _, category, city = call.data.split(":", 2)
    data = await state.get_data()
    logger.info(f"Выбран город '{city}' для telegram_id={call.from_user.id} в категории {category}")

    await state.update_data(city=city)
    tags = await get_category_tags(AD_CATEGORIES[category]["tag_category"])
    if not tags:
        await call.message.edit_text(
            "Нет доступных тегов. Обратитесь к администратору.\n🏠:",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        return

    buttons = [[InlineKeyboardButton(text=name, callback_data=f"tag_select:{id}")] for id, name in tags]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await call.message.edit_text(
        AD_CATEGORIES[category]["texts"]["tags"],
        reply_markup=keyboard
    )
    await call.answer()
    await state.set_state(AdAddForm.tags)

# Выбор другого города
@ad_router.callback_query(F.data.startswith("city_other:"), StateFilter(AdAddForm.city))
async def process_city_other(call: types.CallbackQuery, state: FSMContext):
    category = call.data.split(":", 1)[1]
    logger.info(f"Пользователь {call.from_user.id} выбрал 'Другой город' для категории '{category}'")

    cities = await get_cities()
    main_cities = ["Тбилиси", "Батуми", "Кутаиси", "Гори"]
    other_cities = [city[1] for city in cities if city[1] not in main_cities]
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

# Выбор тегов
@ad_router.callback_query(F.data.startswith("tag_select:"), StateFilter(AdAddForm.tags))
async def process_ad_tags(call: types.CallbackQuery, state: FSMContext):
    tag_id = int(call.data.split(":", 1)[1])
    data = await state.get_data()
    category = data.get("category")

    async for session in get_db():
        result = await session.execute(select(Tag).where(Tag.id == tag_id))
        tag = result.scalar_one_or_none()
        if tag:
            tags = [tag.name] if not AD_CATEGORIES[category]["multiple_tags"] else data.get("tags", []) + [tag.name]
            await state.update_data(tags=tags)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Помощь", callback_data=f"help:{category}:title"),
                 InlineKeyboardButton(text="Назад", callback_data="back")]
            ])
            await call.message.edit_text(
                f"Выбрано: {', '.join(tags)}\n{AD_CATEGORIES[category]['texts']['title']}",
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
        AD_CATEGORIES[category]["texts"]["description"],
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
        [InlineKeyboardButton(text="Подтвердите, что все загружено", callback_data="media_confirm"),
         InlineKeyboardButton(text="Пропустить загрузку медиа", callback_data="media_skip")],
        [InlineKeyboardButton(text="Помощь", callback_data=f"help:{category}:media"),
         InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    await message.answer(
        AD_CATEGORIES[category]["texts"]["media"],
        reply_markup=keyboard
    )
    await state.set_state(AdAddForm.media)


# Загрузка медиа

@ad_router.message(F.photo | F.video, StateFilter(AdAddForm.media))
async def process_ad_media(message: types.Message, state: FSMContext):
    if message.from_user.is_bot:
        logger.debug(f"Сообщение от бота {message.from_user.id} проигнорировано")
        return

    file_id = message.photo[-1].file_id if message.photo else message.video.file_id if message.video else None
    if not file_id:
        logger.debug(f"Нет file_id в сообщении от {message.from_user.id}")
        return

    media_group_id = message.media_group_id
    data = await state.get_data()
    category = data.get("category")
    media_file_ids = data.get("media_file_ids", [])
    media_message_id = data.get("media_message_id")
    media_groups = data.get("media_groups", {})
    last_group_time = data.get("last_group_time", 0)
    current_time = asyncio.get_event_loop().time()
    logger.debug(f"Начало обработки: file_count={len(media_file_ids)}, media_message_id={media_message_id}, media_group_id={media_group_id}")

    if file_id not in media_file_ids:
        media_file_ids.append(file_id)
        if media_group_id:
            # Накопление файлов группы
            group_files = media_groups.get(media_group_id, [])
            group_files.append(file_id)
            media_groups[media_group_id] = group_files
            await state.update_data(media_file_ids=media_file_ids[:10], media_groups=media_groups, last_group_time=current_time)
            logger.debug(f"Добавлен файл в группу: {media_group_id}, files={group_files}")

            # Ждем 1 секунду после последнего файла группы
            await asyncio.sleep(1)
            data = await state.get_data()
            if data.get("last_group_time") == current_time:  # Если время не обновилось, это последний файл
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
                    logger.error(f"Ошибка при обработке медиа для telegram_id={message.from_user.id}: {e}")
                    await message.answer("⚠ Ошибка при загрузке файла. Попробуйте снова.")

                # Автоматический переход к контактам
                await state.set_state(AdAddForm.contacts)
                await _send_contact_options(message, state)  # Исправленный вызов
        else:
            # Одиночный файл
            file_count = len(media_file_ids)
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
                logger.error(f"Ошибка при обработке медиа для telegram_id={message.from_user.id}: {e}")
                await message.answer("⚠ Ошибка при обработке файла. Попробуйте снова.")

            # Автоматический переход к контактам
            await state.set_state(AdAddForm.contacts)
            await _send_contact_options(message, state)  # Исправленный вызов
    else:
        logger.debug(f"Файл {file_id} уже в списке для {message.from_user.id}")


@ad_router.callback_query(F.data == "media_confirm", StateFilter(AdAddForm.media))
async def process_ad_complete(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    media_file_ids = data.get("media_file_ids", [])
    file_count = len(media_file_ids)
    text = f"Загружено {file_count} файлов" if file_count > 0 else "Медиа не загружены"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердите", callback_data="confirm_contact")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    await call.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(AdAddForm.contacts)




# Завершение загрузки медиа
@ad_router.callback_query(F.data == "media_confirm", StateFilter(AdAddForm.media))
async def process_ad_complete(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    media_file_ids = data.get("media_file_ids", [])
    if media_file_ids:
        logger.info(f"Завершена загрузка медиа для telegram_id={call.from_user.id}, файлы: {media_file_ids}")
        await call.message.edit_text(f"Загружено {len(media_file_ids)} файлов")
    else:
        logger.info(f"Завершена загрузка без медиа для telegram_id={call.from_user.id}")
        await call.message.edit_text("Медиа не загружены")
    if call.from_user.is_bot:
        logger.debug(f"Пользователь {call.from_user.id} — бот, дальнейшие действия невозможны")
        await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text="Боты не могут добавлять объявления.\n🏠:",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
    else:
        logger.debug(f"Переход к выбору контактов для пользователя {call.from_user.id}")
        await state.set_state(AdAddForm.contacts)
        await _send_contact_options(call, state)


# Пропуск загрузки медиа
@ad_router.callback_query(F.data == "media_skip", StateFilter(AdAddForm.media))
async def process_ad_skip(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(media_file_ids=None)
    logger.info(f"Пользователь {call.from_user.id} пропустил загрузку медиа")
    await call.message.edit_text("Медиа пропущены")
    if call.from_user.is_bot:
        logger.debug(f"Пользователь {call.from_user.id} — бот, дальнейшие действия невозможны")
        await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text="Боты не могут добавлять объявления.\n🏠:",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
    else:
        logger.debug(f"Переход к выбору контактов для пользователя {call.from_user.id}")
        await state.set_state(AdAddForm.contacts)
        await _send_contact_options(call, state)
    await call.answer()

async def _send_contact_options(message: types.Message, state: FSMContext):
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    data = await state.get_data()
    if message.from_user.is_bot:
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
    buttons.append([InlineKeyboardButton(text="Помощь", callback_data=f"help:{data.get('category', 'unknown')}:contacts"),
                    InlineKeyboardButton(text="Назад", callback_data="back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    logger.debug(f"Отправка сообщения с контактами для {telegram_id}")
    await message.bot.send_message(
        chat_id=message.from_user.id,
        text=AD_CATEGORIES[data.get('category', 'unknown')]["texts"]["contacts"],
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
        await call.message.edit_text("Ошибка: контакт не выбран. Попробуйте снова.\n🏠:", reply_markup=get_main_menu_keyboard())
        await state.clear()
        return

    await state.update_data(contacts=selected_contact)
    preview = (
        f"Ваше объявление:\n"
        f"Категория: {data.get('category', 'не указана')}\n"
        f"Город: {data['city']}\n"
        f"Теги: {', '.join(data['tags']) if data['tags'] else 'нет'}\n"
        f"Название: {data['title']}\n"
        f"Описание: {data['description']}\n"
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

# Ввод дополнительных контактов
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
        f"Ваше объявление:\n"
        f"Категория: {category}\n"
        f"Город: {data['city']}\n"
        f"Теги: {', '.join(data['tags']) if data['tags'] else 'нет'}\n"
        f"Название: {data['title']}\n"
        f"Описание: {data['description']}\n"
        f"Медиа: {'Есть' if data.get('media_file_ids') else 'Нет'}\n"
        f"Контакты: {contacts}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сохранить", callback_data="confirm:save"),
         InlineKeyboardButton(text="Отменить", callback_data="confirm:cancel")]
    ])
    await message.answer(preview, reply_markup=keyboard)
    await state.set_state(AdAddForm.confirm)

# Подтверждение или отмена объявления
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
                await call.message.edit_text("Пользователь не найден. Используйте /start.\n🏠:", reply_markup=get_main_menu_keyboard())
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
                contact_info=data["contacts"]
            )
            logger.info(f"Объявление #{ad_id} добавлено для telegram_id={telegram_id}")
        await call.message.edit_text(
            f"✅ Объявление сохранено и отправлено на модерацию\n🏠:",
            reply_markup=get_main_menu_keyboard()
        )
    elif action == "cancel":
        await call.message.edit_text(
            f"❌ Добавление объявления отменено\n🏠:",
            reply_markup=get_main_menu_keyboard()
        )
    await state.clear()
    await call.answer()

# Обработчик "Назад" для всех шагов
@ad_router.callback_query(F.data == "back", StateFilter(AdAddForm))
async def process_ad_back(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Возврат в главное меню.\n🏠:", reply_markup=get_main_menu_keyboard())
    await state.clear()
    await call.answer()

# Обработчик "Помощь" для всех шагов
@ad_router.callback_query(F.data.startswith("help:"), StateFilter(AdAddForm))
async def process_ad_help(call: types.CallbackQuery, state: FSMContext):
    _, category, step = call.data.split(":", 2)
    data = await state.get_data()
    category = data.get("category", category)
    help_text = AD_CATEGORIES[category]["texts"].get(f"help_{step}", "Помощь для этого шага недоступна.")
    await call.message.bot.send_message(
        chat_id=call.from_user.id,
        text=help_text
    )
    await call.answer()