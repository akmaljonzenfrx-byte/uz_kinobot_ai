from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from config import PREMIUM_PRICES


def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("🔍 AI Qidiruv"), KeyboardButton("🎬 Kod bo'yicha qidiruv")],
        [KeyboardButton("🎭 Janrlar"), KeyboardButton("🔥 TOP Kinolar")],
        [KeyboardButton("👤 Profilim"), KeyboardButton("💎 Premium sotib olish")],
        [KeyboardButton("ℹ️ Yordam")],
    ]
    if is_admin:
        keyboard.append([KeyboardButton("⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def sub_check_keyboard(channels: list[dict]) -> InlineKeyboardMarkup:
    keyboard = []
    for idx, ch in enumerate(channels, 1):
        title = ch.get("title", f"Kanal {idx}")
        url = ch.get("invite_link", "")
        keyboard.append([InlineKeyboardButton(text=f"📢 {title}", url=url)])

    keyboard.append(
        [InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subscription")]
    )
    return InlineKeyboardMarkup(keyboard)


def movie_details_keyboard(movie_code: str, download_views: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text=f"👁 Ko'rishlar: {download_views}", callback_data="none"),
            InlineKeyboardButton(
                text="🚀 Ulashish",
                url=f"https://t.me/share/url?url=https://t.me/&text=Kino%20kodi:%20{movie_code}"
            ),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def profile_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="💳 Balansni to'ldirish", callback_data="top_up_balance")],
        [InlineKeyboardButton(text="💎 Premium sotib olish", callback_data="buy_premium_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def premium_plans_keyboard() -> InlineKeyboardMarkup:
    keyboard = []
    row = []
    for days, price in PREMIUM_PRICES.items():
        btn = InlineKeyboardButton(
            text=f"💎 {days} kun - {price:,} so'm",
            callback_data=f"buy_prem_{days}"
        )
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_profile")])
    return InlineKeyboardMarkup(keyboard)


def genres_keyboard(genres: list[str]) -> InlineKeyboardMarkup:
    keyboard = []
    row = []
    for g in genres:
        btn = InlineKeyboardButton(text=f"🎬 {g}", callback_data=f"genre_{g}")
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text="❌ Yopish", callback_data="close_genres")])
    return InlineKeyboardMarkup(keyboard)


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="admin_add_movie"),
            InlineKeyboardButton(text="🎬 Kinolar ro'yxati", callback_data="admin_manage_movies"),
        ],
        [
            InlineKeyboardButton(text="📢 Majburiy obuna", callback_data="admin_sub_channels"),
            InlineKeyboardButton(text="👤 Foydalanuvchini boshqarish", callback_data="admin_manage_user"),
        ],
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
            InlineKeyboardButton(text="📨 Hammaga xabar", callback_data="admin_broadcast"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_channels_keyboard(channels: list[dict], sub_enabled: bool) -> InlineKeyboardMarkup:
    keyboard = []
    status_text = "🟢 Yoqilgan (O'chirish)" if sub_enabled else "🔴 O'chirilgan (Yoqish)"
    keyboard.append(
        [InlineKeyboardButton(text=f"Majburiy obuna: {status_text}", callback_data="admin_toggle_sub")]
    )

    for ch in channels:
        ch_id = ch.get("channel_id", "")
        title = ch.get("title", ch_id)
        keyboard.append(
            [
                InlineKeyboardButton(text=f"📢 {title}", url=ch.get("invite_link", "https://t.me")),
                InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin_del_chan_{ch_id}"),
            ]
        )

    keyboard.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_add_channel")])
    keyboard.append([InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="admin_main_menu")])
    return InlineKeyboardMarkup(keyboard)


def admin_movie_manage_keyboard(movie_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"admin_edit_movie_{movie_id}"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin_del_movie_{movie_id}"),
        ],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_manage_movies")],
    ]
    return InlineKeyboardMarkup(keyboard)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton("❌ Bekor qilish")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)