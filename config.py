import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN muhit o'zgaruvchisi topilmadi. .env faylini tekshiring!")

_admin_ids_raw: str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()
]

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

PORT: int = int(os.getenv("PORT", "8080"))

DB_PATH: str = os.getenv("DB_PATH", "kino_bot.db")

FREE_AI_DAILY_LIMIT: int = int(os.getenv("FREE_AI_DAILY_LIMIT", "5"))

# Kunlar soni: Narxi (so'mda)
PREMIUM_PRICES: dict[int, int] = {
    7: 15000,
    30: 45000,
    90: 110000,
    365: 350000,
}