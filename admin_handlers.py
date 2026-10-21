import asyncio
import logging
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from config import ADMIN_IDS
from database import (
    activate_premium,
    add_channel,
    add_movie,
    delete_channel,
    delete_movie,
    get_all_movies_for_ai,
    get_all_users,
    get_bot_stats,
    get_channels,
    get_movie_by_id,
    get_sub_required_setting,
    get_user,
    set_sub_required_setting,
    set_user_block,
    update_balance,
    update_movie,
)
from keyboards import (
    admin_channels_keyboard,
    admin_menu_keyboard,
    admin_movie_manage_keyboard,
    cancel_keyboard,
    main_menu_keyboard,
)

logger = logging.getLogger(__name__)

# add_movie states
MOVIE_VIDEO, MOVIE_TITLE, MOVIE_YEAR, MOVIE_GENRE, MOVIE_DESC, MOVIE_CODE = range(6)

# broadcast states
BROADCAST_MESSAGE = range(1)

# user_management states
USER_ID_INPUT, USER_ACTION_SELECT, USER_VALUE_INPUT = range(3)

# channel add state
CHANNEL_INFO_INPUT = 100

# movie edit states
EDIT_MOVIE_SELECT_FIELD, EDIT_MOVIE_VALUE_INPUT = 200, 201


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def admin_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not is_admin(update.effective_user.id):
        if update.message:
            await update.message.reply_text("⛔️ Siz administrator emassiz!")
        return

    text = (
        "⚙️ <b>ADMINISTRATOR BOSHQARUV PANELI</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    kb = admin_menu_keyboard()

    if update.message:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    elif update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await update.effective_chat.send_message(text, parse_mode="HTML", reply_markup=kb)


async def admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.answer("⛔️ Ruxsat berilmagan!", show_alert=True)
        return

    data = query.data

    if data == "admin_main_menu":
        await query.answer()
        await admin_start_handler(update, context)
        return

    elif data == "admin_stats":
        await query.answer()
        stats = await get_bot_stats()
        text = (
            "📊 <b>BOT STATISTIKASI</b>\n\n"
            f"👥 Jami foydalanuvchilar: <b>{stats['total_users']:,}</b> ta\n"
            f"🆕 Bugun qo'shilganlar: <b>{stats['today_users']:,}</b> ta\n"
            f"💎 Premium foydalanuvchilar: <b>{stats['premium_users']:,}</b> ta\n"
            f"🎬 Bazadagi kinolar: <b>{stats['total_movies']:,}</b> ta\n\n"
            "🔥 <b>Eng ko'p ko'rilgan 5 ta kino:</b>\n"
        )
        if stats["top_movies"]:
            for idx, m in enumerate(stats["top_movies"], 1):
                text += f"{idx}. {m['title']} (kodi: {m['code']}) — {m['views']} marta\n"
        else:
            text += "<i>Hozircha ko'rishlar mavjud emas.</i>\n"

        kb = admin_menu_keyboard()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        return

    elif data == "admin_sub_channels":
        await query.answer()
        sub_enabled = await get_sub_required_setting()
        channels = await get_channels()
        kb = admin_channels_keyboard(channels, sub_enabled)
        text = (
            "📢 <b>MAJBURIY OBUNA SOZLAMALARI</b>\n\n"
            f"Holat: <b>{'🟢 Yoqilgan' if sub_enabled else '🔴 O\'chirilgan'}</b>\n"
            f"Ulangan kanallar soni: <b>{len(channels)}</b> ta\n\n"
            "Kanal qo'shish yoki o'chirish uchun tugmalardan foydalaning:"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        return

    elif data == "admin_toggle_sub":
        current_status = await get_sub_required_setting()
        new_status = not current_status
        await set_sub_required_setting(new_status)
        await query.answer(f"Majburiy obuna {'yoqildi' if new_status else 'o\'chirildi'}!", show_alert=True)
        channels = await get_channels()
        kb = admin_channels_keyboard(channels, new_status)
        text = (
            "📢 <b>MAJBURIY OBUNA SOZLAMALARI</b>\n\n"
            f"Holat: <b>{'🟢 Yoqilgan' if new_status else '🔴 O\'chirilgan'}</b>\n"
            f"Ulangan kanallar soni: <b>{len(channels)}</b> ta\n\n"
            "Kanal qo'shish yoki o'chirish uchun tugmalardan foydalaning:"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        return

    elif data.startswith("admin_del_chan_"):
        chan_id = data.replace("admin_del_chan_", "").strip()
        await delete_channel(chan_id)
        await query.answer("Kanal o'chirildi!", show_alert=True)
        sub_enabled = await get_sub_required_setting()
        channels = await get_channels()
        kb = admin_channels_keyboard(channels, sub_enabled)
        text = (
            "📢 <b>MAJBURIY OBUNA SOZLAMALARI</b>\n\n"
            f"Holat: <b>{'🟢 Yoqilgan' if sub_enabled else '🔴 O\'chirilgan'}</b>\n"
            f"Ulangan kanallar soni: <b>{len(channels)}</b> ta\n\n"
            "Kanal qo'shish yoki o'chirish uchun tugmalardan foydalaning:"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        return

    elif data == "admin_manage_movies":
        await query.answer()
        movies = await get_all_movies_for_ai()
        if not movies:
            await query.answer("Bazada kinolar yo'q!", show_alert=True)
            return

        text = "🎬 <b>BAZADAGI KINOLAR RO'YXATI (So'nggi 20 ta):</b>\n\n"
        for m in movies[:20]:
            text += f"🆔 {m['id']} | 🔑 <code>{m['code']}</code> | {m['title']} ({m['year']})\n"
        text += "\n💡 Kinoni tahrirlash yoki o'chirish uchun: <code>/manage_movie &lt;ID&gt;</code> buyrug'ini yuboring."
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())
        return

    elif data.startswith("admin_del_movie_"):
        movie_id = int(data.replace("admin_del_movie_", ""))
        await delete_movie(movie_id)
        await query.answer(f"№{movie_id} kino muvaffaqiyatli o'chirildi!", show_alert=True)
        await admin_start_handler(update, context)
        return


# --- KINO QO'SHISH CONVERSATION ---

async def add_movie_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id

    if not is_admin(user_id):
        return ConversationHandler.END

    msg = "🎬 <b>Yangi kino qo'shish</b>\n\nIltimos, kino videosini (file) yuboring:"
    if query:
        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=cancel_keyboard())
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=cancel_keyboard())
    return MOVIE_VIDEO


async def add_movie_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.video:
        await update.message.reply_text("❌ Iltimos, video fayl yuboring!", reply_markup=cancel_keyboard())
        return MOVIE_VIDEO

    context.user_data["new_movie_file_id"] = update.message.video.file_id
    await update.message.reply_text(
        "✅ Video qabul qilindi.\n\nEndi <b>kino nomini</b> kiriting (Masalan: <i>Titanik</i>):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    return MOVIE_TITLE


async def add_movie_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    title = update.message.text.strip()
    if len(title) < 2:
        await update.message.reply_text("❌ Kino nomi juda qisqa, qayta kiriting:")
        return MOVIE_TITLE

    context.user_data["new_movie_title"] = title
    await update.message.reply_text(
        "📅 Kinoning <b>chiqarilgan yilini</b> kiriting (Masalan: <i>1997</i>):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    return MOVIE_YEAR


async def add_movie_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    year_text = update.message.text.strip()
    if not year_text.isdigit() or len(year_text) != 4:
        await update.message.reply_text("❌ Noto'g'ri yil formati! 4 xonali son kiriting (masalan: 2023):")
        return MOVIE_YEAR

    context.user_data["new_movie_year"] = int(year_text)
    await update.message.reply_text(
        "🎭 Kinoning <b>janrini</b> kiriting (Masalan: <i>Drama, Melodrama, Jangari</i>):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    return MOVIE_GENRE


async def add_movie_genre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    genre = update.message.text.strip()
    context.user_data["new_movie_genre"] = genre
    await update.message.reply_text(
        "📝 Kino haqida <b>qisqacha tavsif (syujet)</b> kiriting:\n"
        "(AI qidiruv aynan shu tavsif orqali ishlaydi, mukammalroq yozing)",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    return MOVIE_DESC


async def add_movie_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    desc = update.message.text.strip()
    context.user_data["new_movie_desc"] = desc
    await update.message.reply_text(
        "🔑 Kino uchun <b>maxsus kod</b> kiriting (Masalan: <i>105</i> yoki <i>avatar2</i>):\n"
        "Agar avtomatik generatsiya qilishni istasangiz <code>auto</code> deb yozing.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    return MOVIE_CODE


async def add_movie_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code_input = update.message.text.strip()
    if code_input.lower() == "auto":
        movies = await get_all_movies_for_ai()
        max_num = 100
        for m in movies:
            if m["code"].isdigit():
                max_num = max(max_num, int(m["code"]))
        movie_code = str(max_num + 1)
    else:
        movie_code = code_input

    try:
        new_id = await add_movie(
            code=movie_code,
            title=context.user_data["new_movie_title"],
            year=context.user_data["new_movie_year"],
            genre=context.user_data["new_movie_genre"],
            description=context.user_data["new_movie_desc"],
            file_id=context.user_data["new_movie_file_id"],
        )
        await update.message.reply_text(
            f"🎉 <b>Kino muvaffaqiyatli qo'shildi!</b>\n\n"
            f"🆔 ID: <b>{new_id}</b>\n"
            f"🎬 Nomi: <b>{context.user_data['new_movie_title']}</b>\n"
            f"📅 Yili: <b>{context.user_data['new_movie_year']}</b>\n"
            f"🎭 Janr: <b>{context.user_data['new_movie_genre']}</b>\n"
            f"🔑 Kodi: <code>{movie_code}</code>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=True),
        )
    except Exception as e:
        logger.exception("Kino qo'shishda xato:")
        await update.message.reply_text(
            f"❌ Xatolik yuz berdi (ehtimol bunday kodli kino mavjud): {e}",
            reply_markup=main_menu_keyboard(is_admin=True),
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Amaliyot bekor qilindi.",
        reply_markup=main_menu_keyboard(is_admin=is_admin(update.effective_user.id)),
    )
    return ConversationHandler.END


def add_movie_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_movie_start, pattern="^admin_add_movie$"),
            CommandHandler("add_movie", add_movie_start),
        ],
        states={
            MOVIE_VIDEO: [
                MessageHandler(filters.VIDEO, add_movie_video),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_conversation),
            ],
            MOVIE_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_title),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_conversation),
            ],
            MOVIE_YEAR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_year),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_conversation),
            ],
            MOVIE_GENRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_genre),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_conversation),
            ],
            MOVIE_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_desc),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_conversation),
            ],
            MOVIE_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_code),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_conversation),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_conversation),
        ],
    )


# --- BROADCAST (HAMMAGA XABAR YUBORISH) CONVERSATION ---

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id

    if not is_admin(user_id):
        return ConversationHandler.END

    msg = (
        "📨 <b>Barcha foydalanuvchilarga xabar yuborish</b>\n\n"
        "Tarqatmoqchi bo'lgan xabaringizni yuboring (matn, rasm yoki video):"
    )
    if query:
        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=cancel_keyboard())
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=cancel_keyboard())
    return BROADCAST_MESSAGE


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    users = await get_all_users()
    total = len(users)
    sent_count = 0
    fail_count = 0

    status_msg = await update.message.reply_text(f"⏳ Xabar tarqatilmoqda... (0/{total})")

    for u in users:
        target_id = u["user_id"]
        try:
            await update.message.copy(chat_id=target_id)
            sent_count += 1
            await asyncio.sleep(0.05)
        except TelegramError:
            fail_count += 1

    try:
        await status_msg.delete()
    except Exception:
        pass

    report = (
        "✅ <b>Xabar tarqatish yakunlandi!</b>\n\n"
        f"👥 Jami foydalanuvchilar: {total} ta\n"
        f"🟢 Muvaffaqiyatli yuborildi: {sent_count} ta\n"
        f"🔴 Yetib bormadi (bloklagan): {fail_count} ta"
    )
    await update.message.reply_text(
        report, parse_mode="HTML", reply_markup=main_menu_keyboard(is_admin=True)
    )
    return ConversationHandler.END


def broadcast_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(broadcast_start, pattern="^admin_broadcast$"),
            CommandHandler("broadcast", broadcast_start),
        ],
        states={
            BROADCAST_MESSAGE: [
                MessageHandler(filters.ALL & ~filters.Regex("^❌ Bekor qilish$"), broadcast_send),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_conversation),
        ],
    )


# --- FOYDALANUVCHINI BOSHQARISH CONVERSATION ---

async def user_manage_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id

    if not is_admin(user_id):
        return ConversationHandler.END

    msg = "👤 <b>Foydalanuvchini boshqarish</b>\n\nFoydalanuvchining Telegram ID raqamini kiriting:"
    if query:
        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=cancel_keyboard())
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=cancel_keyboard())
    return USER_ID_INPUT


async def user_manage_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ ID faqat raqamlardan iborat bo'lishi kerak:")
        return USER_ID_INPUT

    target_id = int(text)
    user = await get_user(target_id)
    if not user:
        await update.message.reply_text(
            f"❌ Bazada ID={target_id} bo'lgan foydalanuvchi topilmadi!",
            reply_markup=main_menu_keyboard(is_admin=True),
        )
        return ConversationHandler.END

    context.user_data["manage_user_id"] = target_id
    status_block = "🔴 Bloklangan" if user.get("is_blocked") else "🟢 Faol"

    info = (
        f"👤 <b>Foydalanuvchi ma'lumotlari:</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"👤 Ism: {user['full_name']}\n"
        f"💳 Balans: {user['balance']:,} so'm\n"
        f"💎 Premium gacha: {user['premium_until'] or 'Yo\'q'}\n"
        f"🔒 Holati: {status_block}\n\n"
        "Bajarmoqchi bo'lgan amalni tanlang (yozib yuboring):\n"
        "1️⃣ <b>balans_qosh</b> (Balansga pul qo'shish)\n"
        "2️⃣ <b>balans_ayir</b> (Balansdan pul ayirish)\n"
        "3️⃣ <b>premium_ber</b> (Kun hisobida Premium berish)\n"
        "4️⃣ <b>bloklash</b> (Foydalanuvchini bloklash)\n"
        "5️⃣ <b>blokdan_ochish</b> (Blokdan chiqarish)"
    )
    await update.message.reply_text(info, parse_mode="HTML", reply_markup=cancel_keyboard())
    return USER_ACTION_SELECT


async def user_manage_action_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    action = update.message.text.strip().lower()
    target_id = context.user_data["manage_user_id"]

    if action in ["bloklash", "4"]:
        await set_user_block(target_id, True)
        await update.message.reply_text(
            f"🔒 Foydalanuvchi (ID: {target_id}) bloklandi!",
            reply_markup=main_menu_keyboard(is_admin=True),
        )
        return ConversationHandler.END

    elif action in ["blokdan_ochish", "5"]:
        await set_user_block(target_id, False)
        await update.message.reply_text(
            f"🔓 Foydalanuvchi (ID: {target_id}) blokdan chiqarildi!",
            reply_markup=main_menu_keyboard(is_admin=True),
        )
        return ConversationHandler.END

    elif action in ["balans_qosh", "1"]:
        context.user_data["manage_action"] = "add_balance"
        await update.message.reply_text("💳 Qo'shiladigan summani kiriting (so'mda):")
        return USER_VALUE_INPUT

    elif action in ["balans_ayir", "2"]:
        context.user_data["manage_action"] = "sub_balance"
        await update.message.reply_text("💳 Ayiriladigan summani kiriting (so'mda):")
        return USER_VALUE_INPUT

    elif action in ["premium_ber", "3"]:
        context.user_data["manage_action"] = "give_premium"
        await update.message.reply_text("💎 Necha kunlik Premium bermoqchisiz (masalan: 30):")
        return USER_VALUE_INPUT

    else:
        await update.message.reply_text("❌ Noto'g'ri tanlov! Ro'yxatdagi variantlardan birini yozing:")
        return USER_ACTION_SELECT


async def user_manage_value_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ Raqam kiriting:")
        return USER_VALUE_INPUT

    val = int(text)
    target_id = context.user_data["manage_user_id"]
    action = context.user_data.get("manage_action")

    if action == "add_balance":
        new_bal = await update_balance(target_id, val)
        await update.message.reply_text(
            f"✅ Foydalanuvchi balansi {val:,} so'mga to'ldirildi. Yangi balans: {new_bal:,} so'm",
            reply_markup=main_menu_keyboard(is_admin=True),
        )
    elif action == "sub_balance":
        new_bal = await update_balance(target_id, -val)
        await update.message.reply_text(
            f"✅ Foydalanuvchi balansidan {val:,} so'm ayirildi. Yangi balans: {new_bal:,} so'm",
            reply_markup=main_menu_keyboard(is_admin=True),
        )
    elif action == "give_premium":
        await activate_premium(target_id, val)
        await update.message.reply_text(
            f"🎉 Foydalanuvchiga {val} kunlik Premium muvaffaqiyatli berildi!",
            reply_markup=main_menu_keyboard(is_admin=True),
        )

    context.user_data.clear()
    return ConversationHandler.END


def user_management_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(user_manage_start, pattern="^admin_manage_user$"),
            CommandHandler("manage_user", user_manage_start),
        ],
        states={
            USER_ID_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, user_manage_id_input),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_conversation),
            ],
            USER_ACTION_SELECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, user_manage_action_select),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_conversation),
            ],
            USER_VALUE_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, user_manage_value_input),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_conversation),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_conversation),
        ],
    )