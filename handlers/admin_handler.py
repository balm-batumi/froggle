from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram import F
from aiogram.fsm.storage.base import StorageKey
from states import AdminForm, AdsViewForm
from database import get_db, User, Advertisement, select, ViewedAds, Subscription
from data.constants import get_main_menu_keyboard
from loguru import logger
from tools.utils import render_ad
from tools.utils import get_navigation_keyboard
from data.categories import CATEGORIES

admin_router = Router()

# Отображает объявления на модерацию и предоставляет кнопки для управления
@admin_router.callback_query(F.data == "admin_moderate")
async def admin_moderate(call: types.CallbackQuery, state: FSMContext):
    logger.debug(f"Вызван admin_moderate с callback_data={call.data}, from_id={call.from_user.id}")
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        # Проверка прав администратора
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_admin:
            logger.warning(f"Пользователь telegram_id={telegram_id} не админ или не найден")
            await call.message.edit_text("У вас нет прав для модерации.\n🏠:", reply_markup=get_main_menu_keyboard())
            return

        # Получение объявлений на модерацию
        result = await session.execute(
            select(Advertisement).where(Advertisement.status == "pending").order_by(Advertisement.id)
        )
        ads = result.scalars().all()
        if not ads:
            logger.debug("Объявлений на модерацию нет")
            await call.message.edit_text("Нет объявлений для модерации.\n🏠:", reply_markup=get_main_menu_keyboard())
            return

        # Рендеринг каждого объявления с кнопками
        for ad in ads:
            buttons = [[
                InlineKeyboardButton(text="Принять", callback_data=f"approve:{ad.id}:[]"),
                InlineKeyboardButton(text="Отклонить", callback_data=f"reject:{ad.id}:[]"),
                InlineKeyboardButton(text="Удалить", callback_data=f"delete:{ad.id}:[]")
            ]]
            message_ids = await render_ad(ad, call.message.bot, call.from_user.id, show_status=True, buttons=buttons, mark_viewed=False)
            logger.debug(f"Рендер объявления #{ad.id}, message_ids={message_ids}")
            # Обновляем callback_data с message_ids
            updated_buttons = [[
                InlineKeyboardButton(text="Принять", callback_data=f"approve:{ad.id}:[{','.join(map(str, message_ids))}]"),
                InlineKeyboardButton(text="Отклонить", callback_data=f"reject:{ad.id}:[{','.join(map(str, message_ids))}]"),
                InlineKeyboardButton(text="Удалить", callback_data=f"delete:{ad.id}:[{','.join(map(str, message_ids))}]")
            ]]
            await call.message.bot.edit_message_reply_markup(
                chat_id=telegram_id,
                message_id=message_ids[-1],
                reply_markup=InlineKeyboardMarkup(inline_keyboard=updated_buttons)
            )

        # Отправка навигационной клавиатуры и сохранение её message_id
        nav_message = await call.message.bot.send_message(
            chat_id=telegram_id,
            text="Режим модерации",
            reply_markup=get_navigation_keyboard()
        )
        await state.update_data(nav_message_id=nav_message.message_id)
        logger.debug(f"Навигационная клавиатура отправлена, message_id={nav_message.message_id}")

    await state.set_state(AdminForm.moderation)
    await call.answer()


# handlers/admin_handler.py
# Обрабатывает одобрение объявления, удаляет все связанные сообщения и уведомляет подписчиков
@admin_router.callback_query(F.data.startswith("approve:"))
async def approve_ad(call: types.CallbackQuery):
    logger.debug(f"Вызван approve_ad с callback_data={call.data}, from_id={call.from_user.id}")
    parts = call.data.split(":")
    ad_id = int(parts[1])
    message_ids = [int(mid) for mid in parts[2].strip("[]").split(",")] if len(parts) > 2 else []
    telegram_id = str(call.from_user.id)
    logger.debug(f"Извлечён ad_id={ad_id}, telegram_id={telegram_id}, message_ids={message_ids}")

    # Удаление всех сообщений, связанных с объявлением
    for msg_id in message_ids:
        try:
            await call.message.bot.delete_message(chat_id=telegram_id, message_id=msg_id)
            logger.debug(f"Удалено сообщение {msg_id} для ad_id={ad_id}")
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения {msg_id} для ad_id={ad_id}: {e}")

    async for session in get_db():
        logger.debug(f"Начало сессии БД для ad_id={ad_id}")
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        if ad:
            ad.status = "approved"
            await session.commit()
            logger.info(f"Объявление #{ad_id} принято модератором telegram_id={telegram_id}")

            # Проверка подписок и уведомление
            subscriptions = await session.execute(select(Subscription))
            subscriptions = subscriptions.scalars().all()
            logger.debug(f"Найдено подписок: {len(subscriptions)}")
            for sub in subscriptions:
                user_result = await session.execute(select(User).where(User.id == sub.user_id))
                user = user_result.scalar_one_or_none()
                if not user:
                    logger.warning(f"Пользователь для подписки user_id={sub.user_id} не найден")
                    continue
                if (
                    ad.city == sub.city and
                    ad.category == sub.category and
                    any(tag in ad.tags for tag in sub.tags)
                ):
                    query = (
                        select(Advertisement)
                        .where(Advertisement.status == "approved")
                        .where(Advertisement.city == sub.city)
                        .where(Advertisement.category == sub.category)
                        .where(~Advertisement.id.in_(
                            select(ViewedAds.advertisement_id)
                            .where(ViewedAds.user_id == sub.user_id)
                        ))
                        .where(Advertisement.tags.overlap(sub.tags))
                    )
                    result = await session.execute(query)
                    pending_ads = result.scalars().all()
                    missed_count = len(pending_ads)
                    if missed_count > 0:
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="Смотреть", callback_data="view_subscription_ads")
                        ]])
                        text = f"У вас {missed_count} непросмотренных объявлений по вашей подписке"
                        try:
                            await call.message.bot.send_message(
                                chat_id=user.telegram_id,
                                text=text,
                                reply_markup=keyboard
                            )
                            logger.info(f"Отправлено уведомление для telegram_id={user.telegram_id}, count={missed_count}")
                        except Exception as e:
                            logger.error(f"Ошибка отправки уведомления для telegram_id={user.telegram_id}: {e}")

            # Отправляем подтверждение модератору
            await call.message.bot.send_message(
                chat_id=telegram_id,
                text=f"Объявление #{ad_id} одобрено"
            )
            # Отправляем навигационную клавиатуру
            await call.message.bot.send_message(
                chat_id=telegram_id,
                text="Режим модерации",
                reply_markup=get_navigation_keyboard()
            )

    await call.answer()
    logger.debug(f"Завершение approve_ad для ad_id={ad_id}")


# Отклоняет объявление, отправляет уведомление владельцу и сохраняет его message_id в состоянии
# Убран импорт dp, используется bot из call для создания FSMContext
@admin_router.callback_query(F.data.startswith("reject:"))
async def reject_ad(call: types.CallbackQuery, state: FSMContext):
    logger.info(f"Вход в reject_ad с callback_data={call.data}, from_id={call.from_user.id}")
    logger.debug(f"Вызван reject_ad с callback_data={call.data}, from_id={call.from_user.id}")
    parts = call.data.split(":")
    ad_id = int(parts[1])
    message_ids = [int(mid) for mid in parts[2].strip("[]").split(",")] if len(parts) > 2 else []
    telegram_id = str(call.from_user.id)
    bot = call.message.bot  # Получаем bot из call
    logger.debug(f"Извлечён ad_id={ad_id}, telegram_id={telegram_id}, message_ids={message_ids}")

    # Удаление всех сообщений, связанных с объявлением
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=telegram_id, message_id=msg_id)
            logger.debug(f"Удалено сообщение {msg_id} для ad_id={ad_id}")
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения {msg_id} для ad_id={ad_id}: {e}")

    async for session in get_db():
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        if ad:
            ad.status = "rejected"
            await session.commit()
            user_result = await session.execute(select(User.telegram_id).where(User.id == ad.user_id))
            user_telegram_id = user_result.scalar_one_or_none()
            if user_telegram_id and user_telegram_id != telegram_id:
                full_text = f"❌: Ваше объявление #{ad_id} отклонено модератором."
                short_text = full_text[:35] + "..." if len(full_text) > 35 else full_text
                msg = await bot.send_message(chat_id=user_telegram_id, text=short_text)
                # Сохраняем message_id уведомления в состоянии пользователя
                notification_state = FSMContext(
                    storage=state.storage,  # Используем storage из текущего state
                    key=StorageKey(bot_id=bot.id, chat_id=int(user_telegram_id), user_id=int(user_telegram_id))
                )
                await notification_state.update_data(rejection_notification_id=msg.message_id)
                logger.debug(f"Уведомление отправлено хозяину telegram_id={user_telegram_id}, message_id={msg.message_id}")

            # Удаление старой навигационной клавиатуры админа
            data = await state.get_data()
            old_nav_message_id = data.get("nav_message_id")
            if old_nav_message_id:
                try:
                    await bot.delete_message(chat_id=telegram_id, message_id=old_nav_message_id)
                    logger.debug(f"Удалена старая навигационная клавиатура, message_id={old_nav_message_id}")
                except Exception as e:
                    logger.error(f"Ошибка удаления старой клавиатуры, message_id={old_nav_message_id}: {e}")

            # Отправка сообщения об отклонении модератору
            reject_message = await bot.send_message(
                chat_id=telegram_id,
                text=f"❌ Объявление #{ad_id} отклонено."
            )
            logger.info(f"Объявление #{ad_id} отклонено модератором telegram_id={telegram_id}, message_id={reject_message.message_id}")

            # Отправка новой навигационной клавиатуры
            nav_message = await bot.send_message(
                chat_id=telegram_id,
                text="Режим модерации",
                reply_markup=get_navigation_keyboard()
            )
            await state.update_data(nav_message_id=nav_message.message_id)
            logger.debug(f"Новая навигационная клавиатура отправлена, message_id={nav_message.message_id}")

    await call.answer()


# Запрашивает подтверждение удаления, редактируя сообщение объявления
@admin_router.callback_query(F.data.startswith("delete:"))
async def delete_ad(call: types.CallbackQuery):
    logger.debug(f"Вызван delete_ad с callback_data={call.data}, from_id={call.from_user.id}")
    parts = call.data.split(":")
    ad_id = int(parts[1])  # Извлекаем ID объявления
    message_ids = parts[2].strip("[]").split(",") if len(parts) > 2 and parts[2] else []  # Извлекаем message_ids
    telegram_id = str(call.from_user.id)
    logger.debug(f"Извлечены ad_id={ad_id}, telegram_id={telegram_id}, message_ids={message_ids}")

    if not message_ids:
        logger.error(f"Нет message_ids для ad_id={ad_id}, невозможно отредактировать сообщение")
        await call.message.bot.send_message(
            chat_id=telegram_id,
            text="Ошибка: не удалось найти сообщение для редактирования."
        )
        await call.answer()
        return

    # Формируем клавиатуру с подтверждением
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Да", callback_data=f"delete_confirm:{ad_id}:[{','.join(message_ids)}]"),
        InlineKeyboardButton(text="Нет", callback_data=f"cancel_delete:{ad_id}:[{','.join(message_ids)}]")
    ]])

    # Редактируем последнее сообщение объявления
    last_message_id = int(message_ids[-1])
    try:
        await call.message.bot.edit_message_text(
            chat_id=telegram_id,
            message_id=last_message_id,
            text=f"{call.message.text}\n\nУдалить объявление #{ad_id}?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        logger.debug(f"Сообщение {last_message_id} отредактировано с запросом подтверждения для ad_id={ad_id}")
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения {last_message_id} для ad_id={ad_id}: {e}")
        await call.message.bot.send_message(
            chat_id=telegram_id,
            text="Ошибка при запросе подтверждения."
        )

    await call.answer()


# Удаляет объявление из базы и чата, заменяя последнее сообщение подтверждением
@admin_router.callback_query(F.data.startswith("delete_confirm:"))
async def delete_ad_confirmed(call: types.CallbackQuery, state: FSMContext):
    logger.debug(f"Вызван delete_ad_confirmed с callback_data={call.data}, from_id={call.from_user.id}")
    parts = call.data.split(":")
    ad_id = int(parts[1])  # Извлекаем ID объявления
    message_ids = parts[2].strip("[]").split(",") if len(parts) > 2 and parts[2] else []  # Извлекаем message_ids
    telegram_id = str(call.from_user.id)
    logger.debug(f"Извлечены ad_id={ad_id}, telegram_id={telegram_id}, message_ids={message_ids}")

    if not message_ids:
        logger.error(f"Нет message_ids для ad_id={ad_id}, невозможно подтвердить удаление")
        await call.message.bot.send_message(
            chat_id=telegram_id,
            text="Ошибка: не удалось подтвердить удаление."
        )
        await call.answer()
        return

    # Удаляем все сообщения, кроме последнего
    last_message_id = int(message_ids[-1])
    for msg_id in message_ids[:-1]:
        try:
            await call.message.bot.delete_message(chat_id=telegram_id, message_id=int(msg_id))
            logger.debug(f"Удалено сообщение {msg_id} для ad_id={ad_id}")
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения {msg_id} для ad_id={ad_id}: {e}")

    async for session in get_db():
        logger.debug(f"Начало сессии БД для ad_id={ad_id}")
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        logger.debug(f"Результат запроса объявления: {ad}")
        if ad:
            user_result = await session.execute(select(User.telegram_id).where(User.id == ad.user_id))
            user_telegram_id = user_result.scalar_one_or_none()
            await session.delete(ad)
            await session.commit()  # Теперь с CASCADE удалит записи из viewed_ads автоматически
            logger.info(f"Объявление #{ad_id} удалено модератором telegram_id={telegram_id}")
            if user_telegram_id and user_telegram_id != telegram_id:
                try:
                    await call.message.bot.send_message(
                        chat_id=user_telegram_id,
                        text=f"🗑 Ваше объявление #{ad_id} удалено модератором."
                    )
                    logger.debug(f"Уведомление отправлено автору telegram_id={user_telegram_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления автору telegram_id={user_telegram_id}: {e}")

    # Редактируем последнее сообщение с подтверждением
    try:
        await call.message.bot.edit_message_text(
            chat_id=telegram_id,
            message_id=last_message_id,
            text=f"🗑 Объявление #{ad_id} удалено.",
            reply_markup=None,
            parse_mode="HTML"
        )
        logger.debug(f"Подтверждение удаления отображено в message_id={last_message_id} для ad_id={ad_id}")
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения {last_message_id} для ad_id={ad_id}: {e}")
        await call.message.bot.send_message(
            chat_id=telegram_id,
            text=f"🗑 Объявление #{ad_id} удалено (ошибка отображения)."
        )

    await state.set_state(AdminForm.moderation)
    await call.answer()


# Отменяет запрос удаления, восстанавливая исходные кнопки объявления
@admin_router.callback_query(F.data.startswith("cancel_delete:"))
async def cancel_delete(call: types.CallbackQuery):
    logger.debug(f"Вызван cancel_delete с callback_data={call.data}, from_id={call.from_user.id}")
    parts = call.data.split(":")
    ad_id = int(parts[1])  # Извлекаем ID объявления
    message_ids = parts[2].strip("[]").split(",") if len(parts) > 2 and parts[2] else []  # Извлекаем message_ids
    telegram_id = str(call.from_user.id)
    logger.debug(f"Извлечены ad_id={ad_id}, telegram_id={telegram_id}, message_ids={message_ids}")

    if not message_ids:
        logger.error(f"Нет message_ids для ad_id={ad_id}, невозможно восстановить кнопки")
        await call.message.bot.send_message(
            chat_id=telegram_id,
            text="Ошибка: не удалось восстановить кнопки."
        )
        await call.answer()
        return

    # Формируем исходные кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Принять", callback_data=f"approve:{ad_id}:[{','.join(message_ids)}]"),
        InlineKeyboardButton(text="Отклонить", callback_data=f"reject:{ad_id}:[{','.join(message_ids)}]"),
        InlineKeyboardButton(text="Удалить", callback_data=f"delete:{ad_id}:[{','.join(message_ids)}]")
    ]])

    # Убираем строку подтверждения из текста
    current_text = call.message.text
    confirmation_line = f"\n\nУдалить объявление #{ad_id}?"
    if confirmation_line in current_text:
        original_text = current_text.replace(confirmation_line, "")
    else:
        original_text = current_text  # Если строка не найдена, оставляем как есть

    # Редактируем сообщение
    last_message_id = int(message_ids[-1])
    try:
        await call.message.bot.edit_message_text(
            chat_id=telegram_id,
            message_id=last_message_id,
            text=original_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        logger.debug(f"Кнопки восстановлены для ad_id={ad_id}, message_id={last_message_id}")
    except Exception as e:
        logger.error(f"Ошибка восстановления кнопок для ad_id={ad_id}, message_id={last_message_id}: {e}")
        await call.message.bot.send_message(
            chat_id=telegram_id,
            text="Ошибка при восстановлении кнопок."
        )

    await call.answer()