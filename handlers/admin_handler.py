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

admin_router = Router()

# Обрабатывает нажатие кнопки "Модерация" и показывает все объявления на модерацию
@admin_router.callback_query(F.data == "admin_moderate")
async def admin_moderate(call: types.CallbackQuery, state: FSMContext):
    logger.debug(f"Вызван admin_moderate с callback_data={call.data}, from_id={call.from_user.id}")
    telegram_id = str(call.from_user.id)
    logger.debug(f"Извлечён telegram_id={telegram_id}")
    async for session in get_db():
        logger.debug("Начало сессии БД")
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        logger.debug(f"Результат запроса юзера: {user}")
        if not user or not user.is_admin:
            logger.warning(f"Пользователь telegram_id={telegram_id} не админ или не найден")
            await call.message.edit_text("У вас нет прав для модерации.\n🏠:", reply_markup=get_main_menu_keyboard())
            return

        result = await session.execute(
            select(Advertisement).where(Advertisement.status == "pending").order_by(Advertisement.id)
        )
        ads = result.scalars().all()
        logger.debug(f"Найдено объявлений на модерацию: {len(ads)}, IDs: {[ad.id for ad in ads]}")
        if not ads:
            logger.debug("Объявлений на модерацию нет")
            await call.message.edit_text("Нет объявлений для модерации.\n🏠:", reply_markup=get_main_menu_keyboard())
            return

        for ad in ads:
            buttons = [
                [InlineKeyboardButton(text="Принять", callback_data=f"approve:{ad.id}"),
                 InlineKeyboardButton(text="Отклонить", callback_data=f"reject:{ad.id}"),
                 InlineKeyboardButton(text="Удалить", callback_data=f"delete:{ad.id}")]
            ]
            logger.debug(f"Рендер объявления #{ad.id} с кнопками: {buttons}")
            await render_ad(ad, call.message.bot, call.from_user.id, show_status=True, buttons=buttons, mark_viewed=False)

        final_buttons = [
            [InlineKeyboardButton(text="Помощь", callback_data="action:help"),
             InlineKeyboardButton(text="Назад", callback_data="action:back")]
        ]
        logger.debug(f"Отправка финальных кнопок: {final_buttons}")
        await call.message.bot.send_message(
            chat_id=telegram_id,
            text="Режим модерации",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=final_buttons)
        )
        logger.debug("Финальные кнопки отправлены")

    logger.debug(f"Установка состояния AdminForm:moderation для telegram_id={telegram_id}")
    await state.set_state(AdminForm.moderation)
    logger.debug("Состояние установлено")
    await call.answer()
    logger.debug("Завершение admin_moderate")


# Обработчик одобрения объявления
@admin_router.callback_query(F.data.startswith("approve:"))
async def approve_ad(call: types.CallbackQuery):
    logger.debug(f"Вызван approve_ad с callback_data={call.data}, from_id={call.from_user.id}")
    ad_id = int(call.data.split(":", 1)[1])
    telegram_id = str(call.from_user.id)
    message_id = call.message.message_id
    logger.debug(f"Извлечён ad_id={ad_id}, telegram_id={telegram_id}, message_id={message_id}")
    async for session in get_db():
        logger.debug(f"Начало сессии БД для ad_id={ad_id}")
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        logger.debug(f"Результат запроса объявления: {ad}")
        if ad:
            ad.status = "approved"
            await session.commit()
            logger.info(f"Объявление #{ad_id} принято модератором telegram_id={telegram_id}")

            # Проверка подписок
            subscriptions = await session.execute(select(Subscription))
            subscriptions = subscriptions.scalars().all()
            logger.debug(f"Найдено подписок: {len(subscriptions)}")
            for sub in subscriptions:
                user_result = await session.execute(select(User).where(User.id == sub.user_id))
                user = user_result.scalar_one_or_none()
                logger.debug(f"Подписка user_id={sub.user_id}, результат поиска юзера: {user}")
                if not user:
                    logger.warning(f"Пользователь для подписки user_id={sub.user_id} не найден")
                    continue
                if (
                    ad.city == sub.city and
                    ad.category == sub.category and
                    any(tag in ad.tags for tag in sub.tags)
                ):
                    logger.debug(f"Совпадение подписки: city={sub.city}, category={sub.category}, tags={sub.tags}")
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
                    logger.debug(f"Найдено непросмотренных объявлений: {missed_count}, IDs: {[ad.id for ad in pending_ads]}")
                    if missed_count > 0:
                        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[[
                            types.InlineKeyboardButton(text="Смотреть", callback_data="view_subscription_ads")
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

            # Удаляем сообщение с одобрённым объявлением
            try:
                await call.message.bot.delete_message(chat_id=telegram_id, message_id=message_id)
                logger.debug(f"Сообщение с ad_id={ad_id} удалено, message_id={message_id}")
            except Exception as e:
                logger.error(f"Ошибка удаления сообщения для ad_id={ad_id}: {e}")

            # Отправляем подтверждение
            logger.debug(f"Отправка подтверждения для ad_id={ad_id}")
            await call.message.bot.send_message(
                chat_id=telegram_id,
                text=f"Объявление #{ad_id} одобрено"
            )

            # Переотправляем кнопки "Помощь" и "Назад" в конец чата
            final_buttons = [
                [InlineKeyboardButton(text="Помощь", callback_data="action:help"),
                 InlineKeyboardButton(text="Назад", callback_data="action:back")]
            ]
            logger.debug(f"Переотправка финальных кнопок для ad_id={ad_id}: {final_buttons}")
            await call.message.bot.send_message(
                chat_id=telegram_id,
                text="Режим модерации",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=final_buttons)
            )

    await call.answer()
    logger.debug(f"Завершение approve_ad для ad_id={ad_id}")


# Отклоняет объявление, отправляет уведомления и обновляет список модерации
@admin_router.callback_query(F.data.startswith("reject:"), StateFilter(AdminForm.moderation))
async def reject_ad(call: types.CallbackQuery, state: FSMContext):
    ad_id = int(call.data.split(":")[1])
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        if ad:
            ad.status = "rejected"
            await session.commit()
            # Получаем telegram_id владельца
            user_result = await session.execute(select(User.telegram_id).where(User.id == ad.user_id))
            user_telegram_id = user_result.scalar_one_or_none()
            if user_telegram_id and user_telegram_id != telegram_id:
                await call.message.bot.send_message(
                    chat_id=user_telegram_id,
                    text=f"❌ Ваше объявление #{ad_id} отклонено модератором."
                )
            # Сообщение модератору
            await call.message.bot.send_message(
                chat_id=telegram_id,
                text=f"❌ Объявление #{ad_id} отклонено."
            )
            logger.info(f"Объявление #{ad_id} отклонено модератором telegram_id={telegram_id}")
            # Обновляем список объявлений
            result = await session.execute(
                select(Advertisement).where(Advertisement.status == "pending").order_by(Advertisement.id)
            )
            ads = result.scalars().all()
            for ad in ads:
                buttons = [
                    [InlineKeyboardButton(text="Принять", callback_data=f"approve:{ad.id}"),
                     InlineKeyboardButton(text="Отклонить", callback_data=f"reject:{ad.id}"),
                     InlineKeyboardButton(text="Удалить", callback_data=f"delete:{ad.id}")]
                ]
                await render_ad(ad, call.message.bot, call.from_user.id, show_status=True, buttons=buttons, mark_viewed=True)
            # Кнопки "Помощь" и "Назад" в конце
            final_buttons = [
                [InlineKeyboardButton(text="Помощь", callback_data="action:help"),
                 InlineKeyboardButton(text="Назад", callback_data="action:back")]
            ]
            await call.message.bot.send_message(
                chat_id=telegram_id,
                text="Режим модерации",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=final_buttons)
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


# Удаляет объявление, отправляет уведомления и обновляет список модерации
@admin_router.callback_query(F.data.startswith("delete_confirm:"), StateFilter(AdminForm.confirm_delete))
async def delete_ad_confirmed(call: types.CallbackQuery, state: FSMContext):
    ad_id = int(call.data.split(":")[1])
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        if ad:
            # Получаем telegram_id владельца перед удалением
            user_result = await session.execute(select(User.telegram_id).where(User.id == ad.user_id))
            user_telegram_id = user_result.scalar_one_or_none()
            await session.delete(ad)
            await session.commit()
            if user_telegram_id and user_telegram_id != telegram_id:
                await call.message.bot.send_message(
                    chat_id=user_telegram_id,
                    text=f"🗑 Ваше объявление #{ad_id} удалено модератором."
                )
            # Сообщение модератору
            await call.message.bot.send_message(
                chat_id=telegram_id,
                text=f"🗑 Объявление #{ad_id} удалено."
            )
            logger.info(f"Объявление #{ad_id} удалено модератором telegram_id={telegram_id}")
            # Обновляем список объявлений
            result = await session.execute(
                select(Advertisement).where(Advertisement.status == "pending").order_by(Advertisement.id)
            )
            ads = result.scalars().all()
            for ad in ads:
                buttons = [
                    [InlineKeyboardButton(text="Принять", callback_data=f"approve:{ad.id}"),
                     InlineKeyboardButton(text="Отклонить", callback_data=f"reject:{ad.id}"),
                     InlineKeyboardButton(text="Удалить", callback_data=f"delete:{ad.id}")]
                ]
                await render_ad(ad, call.message.bot, call.from_user.id, show_status=True, buttons=buttons, mark_viewed=True)
            # Кнопки "Помощь" и "Назад" в конце
            final_buttons = [
                [InlineKeyboardButton(text="Помощь", callback_data="action:help"),
                 InlineKeyboardButton(text="Назад", callback_data="action:back")]
            ]
            await call.message.bot.send_message(
                chat_id=telegram_id,
                text="Режим модерации",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=final_buttons)
            )
    await state.set_state(AdminForm.moderation)
    await call.answer()