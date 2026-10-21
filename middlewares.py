import logging
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from database import (
    get_channels,
    get_or_create_user,
    get_sub_required_setting,
    is_user_blocked,
)
from keyboards import sub_check_keyboard

logger = logging.getLogger(__name__)


async def check_subscription(bot, user_id: int) -> tuple[bool, list[dict]]:
    if user_id in ADMIN_IDS:
        return True, []

    sub_required = await get_sub_required_setting()
    if not sub_required:
        return True, []

    channels = await get_channels()
    if not channels:
        return True, []

    unsubscribed = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(
                chat_id=channel["channel_id"], user_id=user_id
            )
            if member.status in ["left", "kicked"]:
                unsubscribed.append(channel)
        except TelegramError as e:
            logger.warning(
                f"Kanal obunasini tekshirishda xatolik ({channel['channel_id']}): {e}"
            )
            unsubscribed.append(channel)

    if unsubscribed:
        return False, unsubscribed

    return True, []


async def ensure_user_active(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    user = update.effective_user
    if not user:
        return False

    user_id = user.id
    username = user.username or ""
    full_name = user.full_name or ""

    await get_or_create_user(user_id, username, full_name)

    blocked = await is_user_blocked(user_id)
    if blocked:
        if update.message:
            await update.message.reply_text("❌ Siz botdan bloklangansiz!")
        elif update.callback_query:
            await update.callback_query.answer(
                "❌ Siz botdan bloklangansiz!", show_alert=True
            )
        return False

    is_sub, unsub_channels = await check_subscription(context.bot, user_id)
    if not is_sub:
        text = (
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz shart:\n\n"
            "Obuna bo'lgach, '✅ Obunani tekshirish' tugmasini bosing."
        )
        kb = sub_check_keyboard(unsub_channels)

        if update.callback_query:
            if update.callback_query.data != "check_subscription":
                await update.callback_query.answer(
                    "⚠️ Avval kanallarga obuna bo'ling!", show_alert=True
                )
                try:
                    await update.callback_query.edit_message_text(
                        text, reply_markup=kb
                    )
                except Exception:
                    if update.effective_chat:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id, text=text, reply_markup=kb
                        )
        elif update.message:
            await update.message.reply_text(text, reply_markup=kb)

        return False

    return True