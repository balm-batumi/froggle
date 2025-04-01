from aiogram import Router, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram import F
from aiogram.fsm.storage.base import StorageKey
from states import AdminForm, AdsViewForm
from database import get_db, User, Advertisement, select, ViewedAds, Subscription
from data.constants import get_main_menu_keyboard
from loguru import logger
from tools.utils import render_ad, get_navigation_keyboard, delete_messages, notify_user
from sqlalchemy.sql import func

admin_router = Router()

# Утилита для отправки или обновления навигационной клавиатуры
async def send_navigation_keyboard(bot: Bot, chat_id: int, state: FSMContext) -> int:
    """Отправляет навигационную клавиатуру и сохраняет её message_id в состоянии."""
    nav_message = await bot.send_message(
        chat_id=chat_id,
        text="Режим модерации",
        reply_markup=get_navigation_keyboard()
    )
    await state.update_data(nav_message_id=nav_message.message_id)
    logger.debug(f"Навигационная клавиатура отправлена, message_id={nav_message.message_id}")
    return nav_message.message_id

# Отображает объявления на модерацию и предоставляет кнопки для управления
@admin_router.callback_query(F.data == "admin_moderate")
async def admin_moderate(call: CallbackQuery, state: FSMContext):
    logger.debug(f"Вызван admin_moderate с callback_data={call.data}, from_id={call.from_user.id}")
    telegram_id = str(call.from_user.id)
    bot = call.message.bot

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
            message_ids = await render_ad(ad, bot, call.from_user.id, show_status=True, buttons=buttons, mark_viewed=False)
            logger.debug(f"Рендер объявления #{ad.id}, message_ids={message_ids}")
            # Обновляем callback_data с message_ids
            updated_buttons = [[
                InlineKeyboardButton(text="Принять", callback_data=f"approve:{ad.id}:[{','.join(map(str, message_ids))}]"),
                InlineKeyboardButton(text="Отклонить", callback_data=f"reject:{ad.id}:[{','.join(map(str, message_ids))}]"),
                InlineKeyboardButton(text="Удалить", callback_data=f"delete:{ad.id}:[{','.join(map(str, message_ids))}]")
            ]]
            await bot.edit_message_reply_markup(
                chat_id=telegram_id,
                message_id=message_ids[-1],
                reply_markup=InlineKeyboardMarkup(inline_keyboard=updated_buttons)
            )

        # Отправка навигационной клавиатуры
        await send_navigation_keyboard(bot, telegram_id, state)

    await state.set_state(AdminForm.moderation)
    await call.answer()


# Одобряет объявление и уведомляет владельца и подписчиков с оптимизированным подсчетом
@admin_router.callback_query(F.data.startswith("approve:"))
async def approve_ad(call: CallbackQuery, state: FSMContext):
    logger.debug(f"Вызван approve_ad с callback_data={call.data}, from_id={call.from_user.id}")
    parts = call.data.split(":")
    ad_id = int(parts[1])
    message_ids = [int(mid) for mid in parts[2].strip("[]").split(",")] if len(parts) > 2 else []
    telegram_id = str(call.from_user.id)
    bot = call.message.bot

    await delete_messages(bot, telegram_id, message_ids)

    async for session in get_db():
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        if ad:
            ad.status = "approved"
            await session.commit()
            logger.info(f"Объявление #{ad_id} принято модератором telegram_id={telegram_id}")

            user_result = await session.execute(select(User.telegram_id).where(User.id == ad.user_id))
            user_telegram_id = user_result.scalar_one_or_none()
            if user_telegram_id and user_telegram_id != telegram_id:
                full_text = f"✅ Ваше объявление #{ad_id} одобрено и опубликовано."
                short_text = full_text[:35] + "..." if len(full_text) > 35 else full_text
                await notify_user(bot, user_telegram_id, short_text, state)

            # Оптимизированная выборка подписок
            subscriptions = await session.execute(
                select(Subscription)
                .where(Subscription.city == ad.city)
                .where(Subscription.category == ad.category)  # Исправлено с Submission на Subscription
                .where(Subscription.tags.overlap(ad.tags))
            )
            subscriptions = subscriptions.scalars().all()
            logger.debug(f"Найдено релевантных подписок: {len(subscriptions)}")

            for sub in subscriptions:
                user_result = await session.execute(select(User).where(User.id == sub.user_id))
                user = user_result.scalar_one_or_none()
                if not user:
                    logger.warning(f"Пользователь для подписки user_id={sub.user_id} не найден")
                    continue

                # Подсчет непросмотренных объявлений через func.count()
                query = (
                    select(func.count(Advertisement.id))
                    .where(Advertisement.status == "approved")
                    .where(Advertisement.city == sub.city)
                    .where(Advertisement.category == sub.category)
                    .where(~Advertisement.id.in_(
                        select(ViewedAds.advertisement_id).where(ViewedAds.user_id == sub.user_id)))
                    .where(Advertisement.tags.overlap(sub.tags))
                )
                missed_count = await session.scalar(query)

                if missed_count > 0:
                    full_text = f"🔔 По подписке {missed_count} новых объ..❓"
                    short_text = full_text[:35] if len(full_text) > 35 else full_text
                    await notify_user(bot, user.telegram_id, short_text, state)
                    logger.info(f"Отправлено уведомление для telegram_id={user.telegram_id}, count={missed_count}")

            await bot.send_message(chat_id=telegram_id, text=f"Объявление #{ad_id} одобрено")
            await send_navigation_keyboard(bot, telegram_id, state)

    await call.answer()


@admin_router.callback_query(F.data.startswith("reject:"))
async def reject_ad(call: CallbackQuery, state: FSMContext):
    """
    Отклоняет объявление, отправляет уведомление владельцу и обновляет навигацию для модератора.
    """
    logger.debug(f"Вызван reject_ad с callback_data={call.data}, from_id={call.from_user.id}")
    parts = call.data.split(":")
    ad_id = int(parts[1])
    message_ids = [int(mid) for mid in parts[2].strip("[]").split(",")] if len(parts) > 2 else []
    telegram_id = str(call.from_user.id)
    bot = call.message.bot

    await delete_messages(bot, telegram_id, message_ids)

    async for session in get_db():
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        if ad:
            ad.status = "rejected"
            await session.commit()
            user_result = await session.execute(select(User.telegram_id).where(User.id == ad.user_id))
            user_telegram_id = user_result.scalar_one_or_none()
            if user_telegram_id and user_telegram_id != telegram_id:
                full_text = f"❌ Ваше объявление #{ad_id} отклонено модератором."
                short_text = full_text[:35] + "..." if len(full_text) > 35 else full_text
                await notify_user(bot, user_telegram_id, short_text, state)

            data = await state.get_data()
            old_nav_message_id = data.get("nav_message_id")
            if old_nav_message_id:
                await delete_messages(bot, telegram_id, [old_nav_message_id])

            await bot.send_message(chat_id=telegram_id, text=f"❌ Объявление #{ad_id} отклонено.")
            await send_navigation_keyboard(bot, telegram_id, state)

    await call.answer()

# Запрашивает подтверждение удаления, редактируя сообщение объявления
@admin_router.callback_query(F.data.startswith("delete:"))
async def delete_ad(call: CallbackQuery):
    logger.debug(f"Вызван delete_ad с callback_data={call.data}, from_id={call.from_user.id}")
    parts = call.data.split(":")
    ad_id = int(parts[1])
    message_ids = parts[2].strip("[]").split(",") if len(parts) > 2 and parts[2] else []
    telegram_id = str(call.from_user.id)
    bot = call.message.bot

    if not message_ids:
        logger.error(f"Нет message_ids для ad_id={ad_id}, невозможно отредактировать сообщение")
        await bot.send_message(chat_id=telegram_id, text="Ошибка: не удалось найти сообщение для редактирования.")
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
        await bot.edit_message_text(
            chat_id=telegram_id,
            message_id=last_message_id,
            text=f"{call.message.text}\n\nУдалить объявление #{ad_id}?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        logger.debug(f"Сообщение {last_message_id} отредактировано с запросом подтверждения для ad_id={ad_id}")
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения {last_message_id} для ad_id={ad_id}: {e}")
        await bot.send_message(chat_id=telegram_id, text="Ошибка при запросе подтверждения.")

    await call.answer()

@admin_router.callback_query(F.data.startswith("delete_confirm:"))
async def delete_ad_confirmed(call: CallbackQuery, state: FSMContext):
    """
    Удаляет объявление из базы и чата, уведомляет владельца и обновляет навигацию.
    """
    logger.debug(f"Вызван delete_ad_confirmed с callback_data={call.data}, from_id={call.from_user.id}")
    parts = call.data.split(":")
    ad_id = int(parts[1])
    message_ids = parts[2].strip("[]").split(",") if len(parts) > 2 and parts[2] else []
    telegram_id = str(call.from_user.id)
    bot = call.message.bot

    if not message_ids:
        logger.error(f"Нет message_ids для ad_id={ad_id}, невозможно подтвердить удаление")
        await bot.send_message(chat_id=telegram_id, text="Ошибка: не удалось подтвердить удаление.")
        await call.answer()
        return

    last_message_id = message_ids[-1]
    await delete_messages(bot, telegram_id, message_ids[:-1])

    async for session in get_db():
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        if ad:
            user_result = await session.execute(select(User.telegram_id).where(User.id == ad.user_id))
            user_telegram_id = user_result.scalar_one_or_none()
            await session.delete(ad)
            await session.commit()
            logger.info(f"Объявление #{ad_id} удалено модератором telegram_id={telegram_id}")
            if user_telegram_id and user_telegram_id != telegram_id:
                await notify_user(bot, user_telegram_id, f"🗑 Ваше объявление #{ad_id} удалено модератором.", state)

    try:
        await bot.edit_message_text(
            chat_id=telegram_id,
            message_id=int(last_message_id),
            text=f"🗑 Объявление #{ad_id} удалено.",
            reply_markup=None,
            parse_mode="HTML"
        )
        logger.debug(f"Подтверждение удаления отображено в message_id={last_message_id} для ad_id={ad_id}")
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения {last_message_id} для ad_id={ad_id}: {e}")
        await bot.send_message(chat_id=telegram_id, text=f"🗑 Объявление #{ad_id} удалено (ошибка отображения).")

    await send_navigation_keyboard(bot, telegram_id, state)
    await state.set_state(AdminForm.moderation)
    await call.answer()

# Отменяет запрос удаления, восстанавливая исходные кнопки объявления
@admin_router.callback_query(F.data.startswith("cancel_delete:"))
async def cancel_delete(call: CallbackQuery):
    logger.debug(f"Вызван cancel_delete с callback_data={call.data}, from_id={call.from_user.id}")
    parts = call.data.split(":")
    ad_id = int(parts[1])
    message_ids = parts[2].strip("[]").split(",") if len(parts) > 2 and parts[2] else []
    telegram_id = str(call.from_user.id)
    bot = call.message.bot

    if not message_ids:
        logger.error(f"Нет message_ids для ad_id={ad_id}, невозможно восстановить кнопки")
        await bot.send_message(chat_id=telegram_id, text="Ошибка: не удалось восстановить кнопки.")
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
    original_text = current_text.replace(confirmation_line, "") if confirmation_line in current_text else current_text

    # Редактируем сообщение
    last_message_id = int(message_ids[-1])
    try:
        await bot.edit_message_text(
            chat_id=telegram_id,
            message_id=last_message_id,
            text=original_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        logger.debug(f"Кнопки восстановлены для ad_id={ad_id}, message_id={last_message_id}")
    except Exception as e:
        logger.error(f"Ошибка восстановления кнопок для ad_id={ad_id}, message_id={last_message_id}: {e}")
        await bot.send_message(chat_id=telegram_id, text="Ошибка при восстановлении кнопок.")

    await call.answer()