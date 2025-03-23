from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy import select, func
from database import get_db, User, Advertisement, select
from data.constants import get_main_menu_keyboard
from states import AdminForm
from loguru import logger

admin_router = Router()

@admin_router.callback_query(lambda call: call.data == "admin_moderate")
async def moderate_handler(call: types.CallbackQuery):
    """Показывает список объявлений на модерацию."""
    telegram_id = str(call.from_user.id)
    async for session in get_db():
        user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user.scalar_one_or_none()
        if not user or not user.is_admin:
            await call.message.edit_text("❌ У вас нет прав.\n🏠:", reply_markup=get_main_menu_keyboard())
            return

        ads = await session.execute(
            select(Advertisement)
            .where(Advertisement.status == "pending")
            .order_by(Advertisement.created_at.asc())
        )
        ads = ads.scalars().all()
        if not ads:
            await call.message.edit_text("Нет объявлений на модерацию.\n🏠:", reply_markup=get_main_menu_keyboard())
            return

        for ad in ads:
            tags_text = ", ".join(ad.tags) if ad.tags else "Нет тегов"
            text = (
                f"ID: {ad.id}\n"
                f"Категория: {ad.category}\n"
                f"Город: {ad.city}\n"
                f"Название: {ad.title_ru}\n"
                f"Описание: {ad.description_ru}\n"
                f"Теги: {tags_text}\n"
                f"Контакты: {ad.contact_info if ad.contact_info else 'Не указаны'}\n"
                f"Медиа: {'Есть' if ad.media_file_ids else 'Нет'}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Принять", callback_data=f"moderate:approve:{ad.id}"),
                 InlineKeyboardButton(text="Отклонить", callback_data=f"moderate:reject:{ad.id}")],
                [InlineKeyboardButton(text="Удалить", callback_data=f"moderate:delete:{ad.id}")]
            ])
            if ad.media_file_ids and len(ad.media_file_ids) > 0:
                if len(ad.media_file_ids) == 1:
                    try:
                        await call.message.bot.send_photo(
                            chat_id=call.from_user.id,
                            photo=ad.media_file_ids[0],
                            caption=text,
                            reply_markup=keyboard
                        )
                    except Exception as e:
                        if "can't use file of type Video as Photo" in str(e):
                            await call.message.bot.send_video(
                                chat_id=call.from_user.id,
                                video=ad.media_file_ids[0],
                                caption=text,
                                reply_markup=keyboard
                            )
                        else:
                            logger.error(f"Ошибка отправки медиа для объявления ID {ad.id}: {e}")
                            await call.message.bot.send_message(
                                chat_id=call.from_user.id,
                                text=f"{text}\n⚠ Ошибка загрузки медиа",
                                reply_markup=keyboard
                            )
                else:
                    media_group = []
                    for i, file_id in enumerate(ad.media_file_ids[:10]):
                        try:
                            # Пробуем как фото
                            await call.message.bot.send_photo(chat_id=call.from_user.id, photo=file_id)
                            media_group.append(
                                types.InputMediaPhoto(media=file_id, caption=text if i == 0 else None)
                            )
                        except Exception as e:
                            if "can't use file of type Video as Photo" in str(e):
                                # Если видео, используем InputMediaVideo
                                media_group.append(
                                    types.InputMediaVideo(media=file_id, caption=text if i == 0 else None)
                                )
                            else:
                                logger.error(f"Неизвестная ошибка для file_id {file_id} в объявлении ID {ad.id}: {e}")
                                media_group.append(
                                    types.InputMediaPhoto(media=file_id, caption=text if i == 0 else None)
                                )
                    try:
                        await call.message.bot.send_media_group(
                            chat_id=call.from_user.id,
                            media=media_group
                        )
                        await call.message.bot.send_message(
                            chat_id=call.from_user.id,
                            text="Выберите действие:",
                            reply_markup=keyboard
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки медиа-группы для объявления ID {ad.id}: {e}")
                        await call.message.bot.send_message(
                            chat_id=call.from_user.id,
                            text=f"{text}\n⚠ Ошибка загрузки медиа-группы",
                            reply_markup=keyboard
                        )
            else:
                await call.message.bot.send_message(
                    chat_id=call.from_user.id,
                    text=text,
                    reply_markup=keyboard
                )
    await call.message.delete()


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