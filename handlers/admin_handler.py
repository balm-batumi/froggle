from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy import select, func
from database import get_db, User, Advertisement, select
from data.constants import get_main_menu_keyboard
from states import AdminForm
from tools.utils import render_ad
from loguru import logger

admin_router = Router()

# Показывает список объявлений на модерацию с кнопками управления
@admin_router.callback_query(lambda call: call.data == "admin_moderate")
async def moderate_handler(call: types.CallbackQuery):
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user.scalar_one_or_none()
        if not user or not user.is_admin:
            await call.message.edit_text("❌ У вас нет прав.\n:", reply_markup=get_main_menu_keyboard())
            return

        ads = await session.execute(
            select(Advertisement)
            .where(Advertisement.status == "pending")
            .order_by(Advertisement.created_at.asc())
        )
        ads = ads.scalars().all()
        if not ads:
            await call.message.edit_text("Нет объявлений на модерацию.\n:", reply_markup=get_main_menu_keyboard())
            return

        for ad in ads:
            buttons = [
                InlineKeyboardButton(text="Принять", callback_data=f"moderate:approve:{ad.id}"),
                InlineKeyboardButton(text="Отклонить", callback_data=f"moderate:reject:{ad.id}"),
                InlineKeyboardButton(text="Удалить", callback_data=f"moderate:delete:{ad.id}")
            ]
            await render_ad(ad, call.message.bot, call.from_user.id, show_status=True, buttons=buttons)

        # Добавляем кнопки с текстом "Режим Модерации"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Помощь", callback_data="action:help"),
             InlineKeyboardButton(text="Назад", callback_data="action:back")]
        ])
        await call.message.bot.send_message(
            chat_id=call.from_user.id,
            text="Режим Модерации",
            reply_markup=keyboard
        )

@admin_router.callback_query(lambda call: call.data.startswith("moderate:approve:"))
async def approve_ad(call: types.CallbackQuery, state: FSMContext):
    """Одобряет объявление."""
    telegram_id = str(call.from_user.id)
    _, action, ad_id = call.data.split(":")
    ad_id = int(ad_id)

    async for session in get_db():
        user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user.scalar_one_or_none()
        if not user or not user.is_admin:
            await call.answer("❌ У вас нет прав.", show_alert=True)
            return

        ad = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = ad.scalar_one_or_none()
        if ad and ad.status == "pending":
            ad.status = "approved"
            await session.commit()
            logger.info(f"Админ {telegram_id} одобрил объявление ID {ad_id}")
            await call.message.bot.send_message(
                chat_id=call.from_user.id,
                text=f"✅ Объявление #{ad_id} принято\n🏠:",
                reply_markup=get_main_menu_keyboard()
            )
    await call.answer()

@admin_router.callback_query(lambda call: call.data.startswith("moderate:reject:"))
async def reject_ad(call: types.CallbackQuery, state: FSMContext):
    """Отклоняет объявление."""
    telegram_id = str(call.from_user.id)
    _, action, ad_id = call.data.split(":")
    ad_id = int(ad_id)

    async for session in get_db():
        user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user.scalar_one_or_none()
        if not user or not user.is_admin:
            await call.answer("❌ У вас нет прав.", show_alert=True)
            return

        ad = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = ad.scalar_one_or_none()
        if ad and ad.status == "pending":
            ad.status = "rejected"
            await session.commit()
            logger.info(f"Админ {telegram_id} отклонил объявление ID {ad_id}")
            await call.message.bot.send_message(
                chat_id=call.from_user.id,
                text=f"❌ Объявление #{ad_id} отклонено\n🏠:",
                reply_markup=get_main_menu_keyboard()
            )
    await call.answer()

@admin_router.callback_query(lambda call: call.data.startswith("moderate:delete:"))
async def delete_ad(call: types.CallbackQuery, state: FSMContext):
    """Запрашивает подтверждение удаления объявления."""
    telegram_id = str(call.from_user.id)
    _, action, ad_id = call.data.split(":")
    ad_id = int(ad_id)

    async for session in get_db():
        user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user.scalar_one_or_none()
        if not user or not user.is_admin:
            await call.answer("❌ У вас нет прав.", show_alert=True)
            return

        ad = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = ad.scalar_one_or_none()
        if ad:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Подтвердить удаление", callback_data=f"delete_confirm:{ad_id}"),
                 InlineKeyboardButton(text="Отмена", callback_data=f"delete_cancel:{ad_id}")]
            ])
            await call.message.edit_text(
                f"Вы уверены, что хотите удалить объявление #{ad_id}?",
                reply_markup=keyboard
            )
            await state.set_state(AdminForm.confirm_delete)
    await call.answer()

@admin_router.callback_query(F.data.startswith("moderate:delete:"))
async def confirm_delete_ad(call: types.CallbackQuery, state: FSMContext):
    """Подтверждение удаления объявления."""
    telegram_id = str(call.from_user.id)
    _, action, ad_id = call.data.split(":")
    ad_id = int(ad_id)
    async for session in get_db():
        user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user.scalar_one_or_none()
        if not user or not user.is_admin:
            await call.message.edit_text("❌ У вас нет прав.\n🏠:", reply_markup=get_main_menu_keyboard())
            return

        ad = await session.get(Advertisement, ad_id)
        if not ad:
            await call.message.edit_text("Объявление не найдено.\n🏠:", reply_markup=get_main_menu_keyboard())
            return

        await session.delete(ad)
        await session.commit()
        logger.info(f"Админ {telegram_id} удалил объявление ID {ad_id}")
        await call.message.edit_text(f"Объявление #{ad_id} удалено.\n🏠:", reply_markup=get_main_menu_keyboard())
    await call.answer()

@admin_router.callback_query(F.data.startswith("delete_cancel:"), StateFilter(AdminForm.confirm_delete))
async def cancel_delete_ad(call: types.CallbackQuery, state: FSMContext):
    """Отменяет удаление объявления."""
    telegram_id = str(call.from_user.id)
    await call.message.edit_text(
        f"Удаление отменено\n🏠:",
        reply_markup=get_main_menu_keyboard()
    )
    await state.clear()
    await call.answer()