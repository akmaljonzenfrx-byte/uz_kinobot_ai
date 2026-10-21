import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS, FREE_AI_DAILY_LIMIT, PREMIUM_PRICES
from database import (
    activate_premium,
    check_premium_status,
    get_ai_usage_today,
    get_all_movies_for_ai,
    get_genres,
    get_movie_by_code,
    get_movies_by_genre,
    get_or_create_user,
    get_top_movies,
    increment_ai_usage,
    increment_movie_views,
    update_balance,
)
from keyboards import (
    genres_keyboard,
    main_menu_keyboard,
    movie_details_keyboard,
    premium_plans_keyboard,
    profile_keyboard,
)
from middlewares import check_subscription, ensure_user_active
from ai_service import find_movie_with_ai

logger = logging.getLogger(__name__)


async def _send_movie_details(update: Update, context: ContextTypes.DEFAULT_TYPE, movie: dict) -> None:
    """Foydalanuvchiga topilgan kinoni (video va caption) yuborish uchun yordamchi funksiya."""
    await increment_movie_views(movie["id"])
    views_count = movie.get("views", 0) + 1
    
    caption = (
        f"🎬 <b>{movie['title']}</b> ({movie['year']})\n\n"
        f"🎭 <b>Janr:</b> {movie['genre']}\n"
        f"📝 <b>Tavsif:</b> {movie['description']}\n\n"
        f"🔑 <b>Kino kodi:</b> <code>{movie['code']}</code>"
    )
    kb = movie_details_keyboard(movie["code"], views_count)
    chat_id = update.effective_chat.id

    try:
        await context.bot.send_video(
            chat_id=chat_id,
            video=movie["file_id"],
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb,
        )
    except Exception as e:
        logger.error(f"Kino videosini yuborishda xatolik: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🎬 <b>{movie['title']}</b> ({movie['year']})\n\n"
                 f"🎭 <b>Janr:</b> {movie['genre']}\n"
                 f"📝 <b>Tavsif:</b> {movie['description']}\n\n"
                 f"⚠️ <i>Videoni yuklashda xatolik yuz berdi.</i>\n"
                 f"🔑 <b>Kino kodi:</b> <code>{movie['code']}</code>",
            parse_mode="HTML",
            reply_markup=kb,
        )


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start komandasi uchun ishlovchi handler."""
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    full_name = update.effective_user.full_name or ""

    await get_or_create_user(user_id, username, full_name)

    is_active = await ensure_user_active(update, context)
    if not is_active:
        return

    is_admin = user_id in ADMIN_IDS
    kb = main_menu_keyboard(is_admin=is_admin)

    # Deep linking orqali kelgan kino kodini tekshirish (masalan: /start 105)
    if context.args and len(context.args) > 0:
        code_arg = context.args[0].strip()
        movie = await get_movie_by_code(code_arg)
        if movie:
            await _send_movie_details(update, context, movie)
            return

    welcome_text = (
        f"Assalomu alaykum, <b>{full_name}</b>!\n\n"
        f"🎬 <b>Professional Kino Bot</b>ga xush kelibsiz!\n\n"
        f"Siz bot orqali:\n"
        f"▫️ Kino kodini yuborib kinoni yuklab olishingiz;\n"
        f"▫️ Sun'iy intellekt (AI) yordamida kinoni o'z so'zlaringiz bilan tasvirlab topishingiz;\n"
        f"▫️ Janrlar va TOP kinolar ro'yxatini ko'rishingiz mumkin.\n\n"
        f"👇 Quyidagi menyudan kerakli bo'limni tanlang yoki kino kodini yuboring:"
    )

    if update.message:
        await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=kb)


async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """'Obunani tekshirish' tugmasi bosilganda ishlaydigan callback."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    user_id = query.from_user.id

    is_sub, unsub_channels = await check_subscription(context.bot, user_id)
    if is_sub:
        await query.answer("✅ Rahmat! Obuna tasdiqlandi.", show_alert=True)
        try:
            await query.message.delete()
        except Exception:
            pass

        is_admin = user_id in ADMIN_IDS
        kb = main_menu_keyboard(is_admin=is_admin)
        await context.bot.send_message(
            chat_id=user_id,
            text="🎉 Barcha kanallarga muvaffaqiyatli obuna bo'ldingiz!\nBotdan foydalanishingiz mumkin.",
            reply_markup=kb,
        )
    else:
        await query.answer(
            "❌ Siz hali barcha kanallarga obuna bo'lmadingiz. Iltimos, obuna bo'ling!",
            show_alert=True,
        )


async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Foydalanuvchi profili va balans ma'lumotlarini ko'rsatish."""
    is_active = await ensure_user_active(update, context)
    if not is_active:
        return

    user_id = update.effective_user.id
    user_data = await get_or_create_user(
        user_id,
        update.effective_user.username or "",
        update.effective_user.full_name or "",
    )

    is_prem, prem_until = await check_premium_status(user_id)
    ai_used_today = await get_ai_usage_today(user_id)

    prem_status_text = (
        f"🟢 Faol ({prem_until} gacha)" if is_prem else "🔴 Nofaol (Oddiy tarif)"
    )
    limit_text = "♾ Cheksiz" if is_prem else f"{ai_used_today} / {FREE_AI_DAILY_LIMIT} ta"

    profile_text = (
        f"👤 <b>FOYDALANUVCHI PROFILI</b>\n\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"👤 <b>Ism:</b> {user_data.get('full_name', '')}\n"
        f"💳 <b>Balans:</b> {user_data.get('balance', 0):,} so'm\n"
        f"💎 <b>Premium holati:</b> {prem_status_text}\n"
        f"🤖 <b>Bugungi AI qidiruvlar:</b> {limit_text}\n"
    )

    kb = profile_keyboard()

    if update.message:
        await update.message.reply_text(profile_text, parse_mode="HTML", reply_markup=kb)
    elif update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                profile_text, parse_mode="HTML", reply_markup=kb
            )
        except Exception:
            await context.bot.send_message(
                chat_id=user_id, text=profile_text, parse_mode="HTML", reply_markup=kb
            )


async def premium_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Premium tariflar menyusini ko'rsatish."""
    is_active = await ensure_user_active(update, context)
    if not is_active:
        return

    text = (
        "💎 <b>PREMIUM OBUNA</b>\n\n"
        "Premium obunachilarga taqdim etiladigan imkoniyatlar:\n"
        "✨ <b>Cheksiz AI qidiruvi</b> - filmlarni o'z so'zlaringiz bilan qidiring;\n"
        "⚡️ <b>Reklamasiz tajriba</b> va yuqori tezlik;\n"
        "🎯 <b>Kengaytirilgan filtrlar</b> va eksklyuziv imkoniyatlar.\n\n"
        "👇 O'zingizga mos tarif rejasini tanlang:"
    )
    kb = premium_plans_keyboard()

    if update.message:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    elif update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text, parse_mode="HTML", reply_markup=kb
            )
        except Exception:
            if update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=kb,
                )


async def buy_premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Premium xarid qilish callbacki."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "back_to_profile":
        await profile_handler(update, context)
        return

    if data.startswith("buy_prem_"):
        try:
            days = int(data.split("_")[2])
        except (IndexError, ValueError):
            await query.answer("❌ Noto'g me'yoriy parametr!", show_alert=True)
            return

        price = PREMIUM_PRICES.get(days)
        if not price:
            await query.answer("❌ Noto'g'ri tarif tanlandi!", show_alert=True)
            return

        user_data = await get_or_create_user(
            user_id, query.from_user.username or "", query.from_user.full_name or ""
        )
        current_balance = user_data.get("balance", 0)

        if current_balance < price:
            await query.answer(
                f"❌ Balansingizda yetarli mablag' mavjud emas!\n"
                f"Sizda: {current_balance:,} so'm. Kerak: {price:,} so'm.\n"
                f"Iltimos, avval balansingizni to'ldiring.",
                show_alert=True,
            )
            return

        # Balansdan ayirish va Premium faollashtirish
        await update_balance(user_id, -price)
        await activate_premium(user_id, days)

        await query.answer(
            f"🎉 Tabriklaymiz! {days} kunlik Premium obuna faollashtirildi!",
            show_alert=True,
        )
        await profile_handler(update, context)


async def top_movies_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Eng ko'p ko'rilgan TOP kinolarni ko'rsatish."""
    is_active = await ensure_user_active(update, context)
    if not is_active:
        return

    top_movies = await get_top_movies(limit=10)
    if not top_movies:
        await update.message.reply_text("🔥 Hozircha kinolar mavjud emas.")
        return

    text = "🔥 <b>ENG MASHHUR TOP KINOLAR</b>\n\n"
    for idx, movie in enumerate(top_movies, 1):
        text += (
            f"<b>{idx}. {movie['title']}</b> ({movie['year']})\n"
            f"   🎭 Janr: {movie['genre']}\n"
            f"   👁 Ko'rishlar: {movie['views']} ta\n"
            f"   🔑 Kodi: <code>{movie['code']}</code>\n\n"
        )

    text += "💡 Kinoni tomosha qilish uchun uning kodini botga yuboring."
    await update.message.reply_text(text, parse_mode="HTML")


async def genres_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mavjud janrlar ro'yxatini ko'rsatish."""
    is_active = await ensure_user_active(update, context)
    if not is_active:
        return

    genres = await get_genres()
    if not genres:
        await update.message.reply_text("🎭 Hozircha janrlar ro'yxati bo'sh.")
        return

    kb = genres_keyboard(genres)
    await update.message.reply_text(
        "🎭 <b>Janrni tanlang:</b>\n"
        "O'zingizga yoqqan janr ustiga bosing va mos kinolar ro'yxatini oling.",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def genre_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Janr tanlanganda kinolar ro'yxatini chiqarish callbacki."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    data = query.data

    if data == "close_genres":
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    if data.startswith("genre_"):
        genre_name = data.replace("genre_", "").strip()
        movies = await get_movies_by_genre(genre_name, limit=10)

        if not movies:
            await query.answer(f"❌ '{genre_name}' janrida kinolar topilmadi.", show_alert=True)
            return

        text = f"🎭 <b>'{genre_name.upper()}' JANRIDAGI KINOLAR:</b>\n\n"
        for idx, movie in enumerate(movies, 1):
            text += (
                f"<b>{idx}. {movie['title']}</b> ({movie['year']})\n"
                f"📝 {movie['description'][:60]}...\n"
                f"🔑 Kodi: <code>{movie['code']}</code>\n\n"
            )

        text += "💡 Kinoni ko'rish uchun uning kodini botga yuboring."
        await context.bot.send_message(
            chat_id=query.from_user.id, text=text, parse_mode="HTML"
        )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Botdan foydalanish bo'yicha yo'riqnoma."""
    is_active = await ensure_user_active(update, context)
    if not is_active:
        return

    help_text = (
        "ℹ️ <b>BOTDAN FOYDALANISH BO'YICHA YORDAM</b>\n\n"
        "1️⃣ <b>Kino kodi bo'yicha qidiruv:</b>\n"
        "Shunchaki kino kodini (masalan: <code>101</code>) yozib yuboring va bot sizga kinoni yuboradi.\n\n"
        "2️⃣ <b>AI (Sun'iy Intellekt) yordamida qidiruv:</b>\n"
        "Kino nomini bilmasangiz, uning fitnasini yoki voqealarini matn ko'rinishida yozing.\n"
        "<i>Masalan: \"dengizda cho'kib ketgan kema va unga bog'liq sevgi voqeasi\"</i>.\n"
        "AI bazadan siz tasvirlagan kinoni topib beradi.\n\n"
        "3️⃣ <b>Balans va Premium:</b>\n"
        "Oddiy foydalanuvchilar kuniga 5 marta AI qidiruvidan foydalanishi mumkin.\n"
        "Premium egalarida esa limitlar yo'q va reklamasiz tajriba taqdim etiladi.\n\n"
        "📩 Barcha savol va takliflar bo'yicha adminlarimizga murojaat qilishingiz mumkin."
    )
    await update.message.reply_text(help_text, parse_mode="HTML")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Barcha kiruvchi matnli xabarlarni qayta ishlovchi markaziy handler."""
    if not update.message or not update.message.text:
        return

    is_active = await ensure_user_active(update, context)
    if not is_active:
        return

    text = update.message.text.strip()
    user_id = update.effective_user.id

    # Menyu tugmalarini tekshirish
    if text == "🔍 AI Qidiruv":
        await update.message.reply_text(
            "🤖 <b>AI QIDIRUV REJIMI</b>\n\n"
            "Kino nomini bilmasangiz, filmni o'z so'zlaringiz bilan tasvirlab yozing.\n"
            "<i>Masalan: \"kosmosda adashib qolgan astronavt haqidagi fantastik film\"</i>",
            parse_mode="HTML",
        )
        return
    elif text == "🎬 Kod bo'yicha qidiruv":
        await update.message.reply_text(
            "🎬 Kino kodini kiriting (masalan: <code>101</code>):",
            parse_mode="HTML",
        )
        return
    elif text == "🎭 Janrlar":
        await genres_menu_handler(update, context)
        return
    elif text == "🔥 TOP Kinolar":
        await top_movies_handler(update, context)
        return
    elif text == "👤 Profilim":
        await profile_handler(update, context)
        return
    elif text == "💎 Premium sotib olish":
        await premium_menu_handler(update, context)
        return
    elif text == "ℹ️ Yordam":
        await help_handler(update, context)
        return
    elif text == "💳 Balansni to'ldirish" or text == "top_up_balance":
        await update.message.reply_text(
            "💳 Balansni to'ldirish uchun administrator bilan bog'laning:\n"
            "👨‍💻 Admin: @admin_username\n\n"
            "To'lov amali bajarilgach, hisobingizga mablag' o'tkazib beriladi."
        )
        return

    # 1. Kod bo'yicha qidiruv (agar kiritilgan matn kino kodi bo'lsa)
    movie = await get_movie_by_code(text)
    if movie:
        await _send_movie_details(update, context, movie)
        return

    # 2. AI Qidiruv (kod bo'lmasa, AI orqali izlaymiz)
    is_prem, _ = await check_premium_status(user_id)
    if not is_prem:
        used_today = await get_ai_usage_today(user_id)
        if used_today >= FREE_AI_DAILY_LIMIT:
            await update.message.reply_text(
                f"⚠️ <b>Bugungi bepul AI qidiruv limitidan ({FREE_AI_DAILY_LIMIT} ta) foydalandingiz.</b>\n\n"
                f"Cheksiz AI qidiruvi va qo'shimcha qulayliklar uchun 💎 Premium obunani xarid qiling!",
                parse_mode="HTML",
            )
            return

    search_msg = await update.message.reply_text(
        "🧠 <i>Sun'iy intellekt kinoni katalogdan izlamoqda...</i>", parse_mode="HTML"
    )

    catalog = await get_all_movies_for_ai()
    ai_result = await find_movie_with_ai(text, catalog)

    await increment_ai_usage(user_id)

    try:
        await search_msg.delete()
    except Exception:
        pass

    if ai_result.get("found") and ai_result.get("exact_match"):
        matched_movie = ai_result["exact_match"]
        reason = ai_result.get("reasoning", "")
        if reason:
            await update.message.reply_text(f"💡 <b>Topildi:</b> {reason}", parse_mode="HTML")
        await _send_movie_details(update, context, matched_movie)
    elif ai_result.get("suggestions"):
        suggestions = ai_result["suggestions"]
        resp_text = "❌ <b>Aniq mos keladigan film topilmadi.</b>\n\n"
        resp_text += "🔍 Lekin quyidagi kinolar yaqin bo'lishi mumkin:\n\n"
        for idx, m in enumerate(suggestions, 1):
            resp_text += (
                f"<b>{idx}. {m['title']}</b> ({m['year']})\n"
                f"🎭 Janr: {m['genre']}\n"
                f"🔑 Kodi: <code>{m['code']}</code>\n\n"
            )
        resp_text += "💡 Kinoni ko'rish uchun uning kodini yuboring."
        await update.message.reply_text(resp_text, parse_mode="HTML")
    else:
        await update.message.reply_text(
            "❌ Kechirasiz, siz kiritgan tavsif bo'yicha katalogimizdan hech qanday kino topilmadi.\n\n"
            "💡 Nomi yoki kalit so'zlarni boshqacharoq yozib ko'ring yoki kino kodini yuboring."
        )