import logging
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import ADMIN_IDS, BOT_TOKEN
from database import add_channel, get_movie_by_id, init_db
from keep_alive import keep_alive
from keyboards import admin_movie_manage_keyboard
from user_handlers import (
    buy_premium_callback,
    check_sub_callback,
    genre_select_callback,
    genres_menu_handler,
    handle_text_message,
    help_handler,
    premium_menu_handler,
    profile_handler,
    start_handler,
    top_movies_handler,
)
from admin_handlers import (
    add_movie_conversation,
    admin_callbacks,
    admin_start_handler,
    broadcast_conversation,
    user_management_conversation,
)

# Logging sozlamalari
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def admin_add_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kanal qo'shish yo'riqnomasini ko'rsatish callbacki."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    text = (
        "➕ <b>KANAL QO'SHISH YO'RIQNOMASI</b>\n\n"
        "1. Botni kanalingizga qo'shing va unga <b>Administrator</b> huquqini bering.\n"
        "2. Quyidagi formatda buyruq yuboring:\n\n"
        "<code>/add_channel &lt;channel_id&gt; &lt;sarlavha&gt; &lt;taklif_havolasi&gt;</code>\n\n"
        "<b>Misol:</b>\n"
        "<code>/add_channel -1001234567890 Kino_Kanal https://t.me/kino_kanal_link</code>"
    )
    await query.message.reply_text(text, parse_mode="HTML")


async def add_channel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Adminlar uchun kanal qo'shish buyrug'i."""
    if not update.effective_user or update.effective_user.id not in ADMIN_IDS:
        return

    args = context.args
    if not args or len(args) < 3:
        await update.message.reply_text(
            "❌ <b>Noto'g'ri format!</b>\n\n"
            "<b>Foydalanish:</b>\n"
            "<code>/add_channel &lt;channel_id&gt; &lt;sarlavha&gt; &lt;taklif_havolasi&gt;</code>\n\n"
            "<b>Misol:</b>\n"
            "<code>/add_channel -1001234567890 Bosh_Kanal https://t.me/+abc123xyz</code>",
            parse_mode="HTML",
        )
        return

    channel_id = args[0].strip()
    title = args[1].replace("_", " ").strip()
    invite_link = args[2].strip()

    try:
        await add_channel(channel_id, title, invite_link)
        await update.message.reply_text(
            f"✅ <b>Kanal muvaffaqiyatli qo'shildi!</b>\n\n"
            f"📢 Title: <b>{title}</b>\n"
            f"🆔 ID: <code>{channel_id}</code>\n"
            f"🔗 Link: {invite_link}",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Kanal qo'shishda xatolik: {e}")
        await update.message.reply_text(f"❌ Xatolik yuz berdi: {e}")


async def manage_movie_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Adminlar uchun kinoni ID bo'yicha boshqarish buyrug'i."""
    if not update.effective_user or update.effective_user.id not in ADMIN_IDS:
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "❌ <b>Noto'g'ri format!</b>\n"
            "Foydalanish: <code>/manage_movie &lt;ID&gt;</code> (masalan: <code>/manage_movie 1</code>)",
            parse_mode="HTML",
        )
        return

    movie_id = int(context.args[0])
    movie = await get_movie_by_id(movie_id)
    if not movie:
        await update.message.reply_text(f"❌ ID={movie_id} bo'lgan kino topilmadi.")
        return

    text = (
        f"🎬 <b>KINONI BOSHQARISH</b>\n\n"
        f"🆔 ID: <b>{movie['id']}</b>\n"
        f"🔑 Kodi: <code>{movie['code']}</code>\n"
        f"🎬 Nomi: <b>{movie['title']}</b> ({movie['year']})\n"
        f"🎭 Janr: <b>{movie['genre']}</b>\n"
        f"👁 Ko'rishlar: <b>{movie['views']} ta</b>\n"
        f"📝 Tavsif: {movie['description']}"
    )
    kb = admin_movie_manage_keyboard(movie_id)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def post_init(application) -> None:
    """Bot ishga tushishidan oldin ma'lumotlar bazasini initsializatsiya qilish."""
    await init_db()
    logger.info("Ma'lumotlar bazasi tayyorlandi va bot faollashtirildi.")


def main() -> None:
    """Botni ishga tushirish uchun asosiy kirish nuqtasi."""
    # Render / Cloud serverlar uchun Keep-Alive serverni ishga tushirish
    keep_alive()

    # Application qurish
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Conversation handlerlarni ro'yxatga olish (ular oddiy handlerlardan oldin bo'lishi kerak)
    application.add_handler(add_movie_conversation())
    application.add_handler(broadcast_conversation())
    application.add_handler(user_management_conversation())

    # Komanda handlerlari
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("admin", admin_start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("profile", profile_handler))
    application.add_handler(CommandHandler("top", top_movies_handler))
    application.add_handler(CommandHandler("genres", genres_menu_handler))
    application.add_handler(CommandHandler("premium", premium_menu_handler))
    application.add_handler(CommandHandler("add_channel", add_channel_cmd))
    application.add_handler(CommandHandler("manage_movie", manage_movie_cmd))

    # Callback Query handlerlari
    application.add_handler(
        CallbackQueryHandler(check_sub_callback, pattern="^check_subscription$")
    )
    application.add_handler(
        CallbackQueryHandler(buy_premium_callback, pattern="^(buy_prem_|back_to_profile)")
    )
    application.add_handler(
        CallbackQueryHandler(genre_select_callback, pattern="^(genre_|close_genres)")
    )
    application.add_handler(
        CallbackQueryHandler(admin_add_channel_callback, pattern="^admin_add_channel$")
    )
    application.add_handler(
        CallbackQueryHandler(admin_callbacks, pattern="^admin_")
    )

    # Barcha kiruvchi matnli xabarlar uchun handler (Eng oxirida bo'lishi shart)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )

    # Botni polling orqali yuritish
    logger.info("Bot muvaffaqiyatli ishga tushirildi. Polling boshlanmoqda...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()