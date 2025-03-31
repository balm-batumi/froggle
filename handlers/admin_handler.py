# handlers/admin_handler.py
# Обработчики для админских функций Froggle
from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram import F
from states import AdminForm, AdsViewForm
from database import get_db, User, Advertisement, select, ViewedAds, Subscription
from data.constants import get_main_menu_keyboard
from loguru import logger
from tools.utils import render_ad
from tools.utils import get_navigation_keyboard
from data.categories import CATEGORIES

admin_router = Router()

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

        # Рендеринг каждого объявления
        for ad in ads:
            # Сначала рендерим объявление без кнопок
            message_ids = await render_ad(ad, call.message.bot, call.from_user.id, show_status=True, mark_viewed=False)
            # Формируем кнопки с использованием message_ids
            buttons = [
                [InlineKeyboardButton(text="Принять", callback_data=f"approve:{ad.id}:[{','.join(map(str, message_ids))}]"),
                 InlineKeyboardButton(text="Отклонить", callback_data=f"reject:{ad.id}:[{','.join(map(str, message_ids))}]"),
                 InlineKeyboardButton(text="Удалить", callback_data=f"delete:{ad.id}:[{','.join(map(str, message_ids))}]")]
            ]
            # Формируем полный текст объявления
            ad_text = f"<b>{CATEGORIES[ad.category]['display_name']}</b> в {ad.city}\n"
            ad_text += f"🏷️ {', '.join(ad.tags)}\n" if ad.tags else ""
            ad_text += f"📌 <b>{ad.title_ru}</b>\n" if ad.title_ru else ""
            ad_text += f"{ad.description_ru}\n" if ad.description_ru else ""
            ad_text += f"💰 {ad.price}\n" if ad.price else "💰 без цены\n"
            ad_text += f"📞 {ad.contact_info}\n" if ad.contact_info else ""
            ad_text += f"Статус: {ad.status}"
            logger.debug(f"Полный текст объявления #{ad.id}: {ad_text}")
            # Редактируем последнее сообщение, добавляя кнопки
            await call.message.bot.edit_message_text(
                text=ad_text,
                chat_id=telegram_id,
                message_id=message_ids[-1],
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML"
            )
            logger.debug(f"Рендер объявления #{ad.id}, message_ids={message_ids}")

        # Отправка навигационной клавиатуры
        await call.message.bot.send_message(
            chat_id=telegram_id,
            text="Режим модерации",
            reply_markup=get_navigation_keyboard()
        )

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


# handlers/admin_handler.py
# Обрабатывает отклонение объявления, удаляет все связанные сообщения и уведомляет пользователя
@admin_router.callback_query(F.data.startswith("reject:"))
async def reject_ad(call: types.CallbackQuery, state: FSMContext):
    logger.debug(f"Вызван reject_ad с callback_data={call.data}, from_id={call.from_user.id}")
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
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        if ad:
            ad.status = "rejected"
            await session.commit()
            user_result = await session.execute(select(User.telegram_id).where(User.id == ad.user_id))
            user_telegram_id = user_result.scalar_one_or_none()
            if user_telegram_id and user_telegram_id != telegram_id:
                await call.message.bot.send_message(
                    chat_id=user_telegram_id,
                    text=f"❌ Ваше объявление #{ad_id} отклонено модератором."
                )
            await call.message.bot.send_message(
                chat_id=telegram_id,
                text=f"❌ Объявление #{ad_id} отклонено."
            )
            logger.info(f"Объявление #{ad_id} отклонено модератором telegram_id={telegram_id}")
            # Отправка навигационной клавиатуры
            await call.message.bot.send_message(
                chat_id=telegram_id,
                text="Режим модерации",
                reply_markup=get_navigation_keyboard()
            )

    await call.answer()


# Обработчик удаления объявления
@admin_router.callback_query(F.data.startswith("delete:"))
async def delete_ad(call: types.CallbackQuery):
    logger.debug(f"Вызван delete_ad с callback_data={call.data}, from_id={call.from_user.id}")
    ad_id = int(call.data.split(":", 1)[1])
    telegram_id = str(call.from_user.id)
    logger.debug(f"Извлечён ad_id={ad_id}, telegram_id={telegram_id}")
    async for session in get_db():
        logger.debug(f"Начало сессии БД для ad_id={ad_id}")
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        logger.debug(f"Результат запроса объявления: {ad}")
        if ad:
            await session.delete(ad)
            await session.commit()
            logger.info(f"Объявление #{ad_id} удалено модератором telegram_id={telegram_id}")

    logger.debug(f"Отправка подтверждения для ad_id={ad_id}")
    await call.message.bot.send_message(
        chat_id=telegram_id,
        text="Объявление удалено"
    )
    await call.answer()
    logger.debug(f"Завершение delete_ad для ad_id={ad_id}")


# handlers/admin_handler.py
# Обрабатывает подтверждение удаления объявления, удаляет все связанные сообщения и само объявление
@admin_router.callback_query(F.data.startswith("delete_confirm:"))
async def delete_ad_confirmed(call: types.CallbackQuery, state: FSMContext):
    logger.debug(f"Вызван delete_ad_confirmed с callback_data={call.data}, from_id={call.from_user.id}")
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
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        if ad:
            user_result = await session.execute(select(User.telegram_id).where(User.id == ad.user_id))
            user_telegram_id = user_result.scalar_one_or_none()
            await session.delete(ad)
            await session.commit()
            if user_telegram_id and user_telegram_id != telegram_id:
                await call.message.bot.send_message(
                    chat_id=user_telegram_id,
                    text=f"🗑 Ваше объявление #{ad_id} удалено модератором."
                )
            await call.message.bot.send_message(
                chat_id=telegram_id,
                text=f"🗑 Объявление #{ad_id} удалено."
            )
            logger.info(f"Объявление #{ad_id} удалено модератором telegram_id={telegram_id}")
            # Отправка навигационной клавиатуры
            await call.message.bot.send_message(
                chat_id=telegram_id,
                text="Режим модерации",
                reply_markup=get_navigation_keyboard()
            )

    await state.set_state(AdminForm.moderation)
    await call.answer()