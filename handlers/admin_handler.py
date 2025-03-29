# handlers/admin_handler.py
# Обработчики для админских функций Froggle
from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram import F
from states import AdminForm, AdsViewForm
from database import get_db, User, Advertisement, select
from data.constants import get_main_menu_keyboard
from loguru import logger
from tools.utils import render_ad

admin_router = Router()

# Обрабатывает нажатие кнопки "Модерация" и показывает все объявления на модерацию
@admin_router.callback_query(F.data == "admin_moderate", StateFilter(None, AdsViewForm.select_category))
async def admin_moderate(call: types.CallbackQuery, state: FSMContext):
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_admin:
            await call.message.edit_text("У вас нет прав для модерации.\n🏠:", reply_markup=get_main_menu_keyboard())
            return

        result = await session.execute(
            select(Advertisement).where(Advertisement.status == "pending").order_by(Advertisement.id)
        )
        ads = result.scalars().all()
        logger.debug(f"Найдено объявлений на модерацию: {len(ads)}, IDs: {[ad.id for ad in ads]}")
        if not ads:
            await call.message.edit_text("Нет объявлений для модерации.\n🏠:", reply_markup=get_main_menu_keyboard())
            return

        for ad in ads:
            buttons = [
                [InlineKeyboardButton(text="Принять", callback_data=f"approve:{ad.id}"),
                 InlineKeyboardButton(text="Отклонить", callback_data=f"reject:{ad.id}"),
                 InlineKeyboardButton(text="Удалить", callback_data=f"delete:{ad.id}")]
            ]
            await render_ad(ad, call.message.bot, call.from_user.id, show_status=True, buttons=buttons, mark_viewed=True)

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


# Одобряет объявление, отправляет уведомление админу и обновляет список модерации
@admin_router.callback_query(F.data.startswith("approve:"), StateFilter(AdminForm.moderation))
async def approve_ad(call: types.CallbackQuery, state: FSMContext):
    ad_id = int(call.data.split(":")[1])
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        if ad:
            ad.status = "approved"
            await session.commit()
            # Отправляем уведомление админу (тебе) в твой чат с Froggle
            await call.message.bot.send_message(
                chat_id=8162326543,  # Твой чат с Froggle
                text=f"✅ Объявление #{ad_id} успешно принято."
            )
            logger.info(f"Объявление #{ad_id} принято модератором telegram_id={telegram_id}")
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


@admin_router.callback_query(F.data.startswith("delete:"), StateFilter(AdminForm.moderation))
async def delete_ad(call: types.CallbackQuery, state: FSMContext):
    ad_id = int(call.data.split(":")[1])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Да", callback_data=f"delete_confirm:{ad_id}"),
        InlineKeyboardButton(text="Нет", callback_data="action:back")
    ]])
    await call.message.edit_text(
        f"Вы точно хотите удалить объявление #{ad_id}?",
        reply_markup=keyboard
    )
    await state.set_state(AdminForm.confirm_delete)
    await call.answer()


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