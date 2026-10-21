import asyncio
import datetime
import logging
import sqlite3
from typing import Any
from config import DB_PATH

logger = logging.getLogger(__name__)


def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
    fields = [column[0] for column in cursor.description]
    return dict(zip(fields, row))


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


async def init_db() -> None:
    def _create_tables() -> None:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    balance INTEGER DEFAULT 0,
                    premium_until TEXT DEFAULT NULL,
                    is_blocked INTEGER DEFAULT 0,
                    ai_requests_today INTEGER DEFAULT 0,
                    last_ai_date TEXT DEFAULT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS movies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    genre TEXT NOT NULL,
                    description TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    views INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    invite_link TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            cursor.execute(
                """
                INSERT OR IGNORE INTO settings (key, value)
                VALUES ('sub_required', '1');
                """
            )
            conn.commit()

    await asyncio.to_thread(_create_tables)
    logger.info("Ma'lumotlar bazasi muvaffaqiyatli ishga tushirildi.")


async def get_user(user_id: int) -> dict | None:
    def _get() -> dict | None:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone()

    return await asyncio.to_thread(_get)


async def register_user(user_id: int, username: str, full_name: str) -> None:
    def _register() -> None:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (user_id, username, full_name, created_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name;
                """,
                (user_id, username, full_name),
            )
            conn.commit()

    await asyncio.to_thread(_register)


async def get_or_create_user(user_id: int, username: str, full_name: str) -> dict:
    await register_user(user_id, username, full_name)
    user = await get_user(user_id)
    if user is None:
        return {
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "balance": 0,
            "premium_until": None,
            "is_blocked": 0,
            "ai_requests_today": 0,
            "last_ai_date": None,
        }
    return user


async def update_balance(user_id: int, amount: int) -> int:
    def _update() -> int:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users
                SET balance = MAX(0, balance + ?)
                WHERE user_id = ?;
                """,
                (amount, user_id),
            )
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            conn.commit()
            return row["balance"] if row else 0

    return await asyncio.to_thread(_update)


async def activate_premium(user_id: int, days: int) -> None:
    def _activate() -> None:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT premium_until FROM users WHERE user_id = ?", (user_id,)
            )
            row = cursor.fetchone()
            now = datetime.datetime.now(datetime.timezone.utc)
            current_until = None
            if row and row.get("premium_until"):
                try:
                    current_until = datetime.datetime.fromisoformat(row["premium_until"])
                    if current_until.tzinfo is None:
                        current_until = current_until.replace(tzinfo=datetime.timezone.utc)
                except ValueError:
                    current_until = None

            if current_until and current_until > now:
                new_until = current_until + datetime.timedelta(days=days)
            else:
                new_until = now + datetime.timedelta(days=days)

            new_until_str = new_until.strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "UPDATE users SET premium_until = ? WHERE user_id = ?",
                (new_until_str, user_id),
            )
            conn.commit()

    await asyncio.to_thread(_activate)


async def check_premium_status(user_id: int) -> tuple[bool, str | None]:
    def _check() -> tuple[bool, str | None]:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT premium_until FROM users WHERE user_id = ?", (user_id,)
            )
            row = cursor.fetchone()
            if not row or not row.get("premium_until"):
                return False, None

            now = datetime.datetime.now(datetime.timezone.utc)
            try:
                until = datetime.datetime.fromisoformat(row["premium_until"])
                if until.tzinfo is None:
                    until = until.replace(tzinfo=datetime.timezone.utc)
                if until > now:
                    return True, until.strftime("%d.%m.%Y %H:%M")
                return False, None
            except ValueError:
                return False, None

    return await asyncio.to_thread(_check)


async def increment_ai_usage(user_id: int) -> int:
    def _increment() -> int:
        today_str = datetime.date.today().isoformat()
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ai_requests_today, last_ai_date FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return 1

            if row["last_ai_date"] == today_str:
                new_count = (row["ai_requests_today"] or 0) + 1
            else:
                new_count = 1

            cursor.execute(
                """
                UPDATE users
                SET ai_requests_today = ?, last_ai_date = ?
                WHERE user_id = ?
                """,
                (new_count, today_str, user_id),
            )
            conn.commit()
            return new_count

    return await asyncio.to_thread(_increment)


async def get_ai_usage_today(user_id: int) -> int:
    def _get() -> int:
        today_str = datetime.date.today().isoformat()
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ai_requests_today, last_ai_date FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return 0
            if row["last_ai_date"] == today_str:
                return row["ai_requests_today"] or 0
            return 0

    return await asyncio.to_thread(_get)


async def add_movie(
    code: str, title: str, year: int, genre: str, description: str, file_id: str
) -> int:
    def _add() -> int:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO movies (code, title, year, genre, description, file_id, views, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, datetime('now'))
                """,
                (code.strip(), title.strip(), year, genre.strip(), description.strip(), file_id.strip()),
            )
            conn.commit()
            return cursor.lastrowid

    return await asyncio.to_thread(_add)


async def get_movie_by_code(code: str) -> dict | None:
    def _get() -> dict | None:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM movies WHERE code = ?", (code.strip(),))
            return cursor.fetchone()

    return await asyncio.to_thread(_get)


async def get_movie_by_id(movie_id: int) -> dict | None:
    def _get() -> dict | None:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
            return cursor.fetchone()

    return await asyncio.to_thread(_get)


async def update_movie(
    movie_id: int, title: str, year: int, genre: str, description: str
) -> None:
    def _update() -> None:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE movies
                SET title = ?, year = ?, genre = ?, description = ?
                WHERE id = ?
                """,
                (title.strip(), year, genre.strip(), description.strip(), movie_id),
            )
            conn.commit()

    await asyncio.to_thread(_update)


async def delete_movie(movie_id: int) -> None:
    def _delete() -> None:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
            conn.commit()

    await asyncio.to_thread(_delete)


async def increment_movie_views(movie_id: int) -> None:
    def _increment() -> None:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE movies SET views = views + 1 WHERE id = ?", (movie_id,)
            )
            conn.commit()

    await asyncio.to_thread(_increment)


async def get_all_movies_for_ai() -> list[dict]:
    def _get_all() -> list[dict]:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, code, title, year, genre, description FROM movies ORDER BY id DESC"
            )
            return cursor.fetchall()

    return await asyncio.to_thread(_get_all)


async def get_top_movies(limit: int = 10) -> list[dict]:
    def _get_top() -> list[dict]:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM movies
                ORDER BY views DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return cursor.fetchall()

    return await asyncio.to_thread(_get_top)


async def get_movies_by_genre(genre: str, limit: int = 10, offset: int = 0) -> list[dict]:
    def _get() -> list[dict]:
        with _get_connection() as conn:
            cursor = conn.cursor()
            pattern = f"%{genre.strip()}%"
            cursor.execute(
                """
                SELECT * FROM movies
                WHERE genre LIKE ?
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (pattern, limit, offset),
            )
            return cursor.fetchall()

    return await asyncio.to_thread(_get)


async def get_genres() -> list[str]:
    def _get_genres() -> list[str]:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT genre FROM movies WHERE genre IS NOT NULL AND genre != ''")
            rows = cursor.fetchall()
            genres_set = set()
            for row in rows:
                parts = [g.strip().capitalize() for g in row["genre"].replace("/", ",").split(",") if g.strip()]
                genres_set.update(parts)
            return sorted(list(genres_set))

    return await asyncio.to_thread(_get_genres)


async def set_user_block(user_id: int, is_blocked: bool) -> None:
    def _set_block() -> None:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET is_blocked = ? WHERE user_id = ?",
                (1 if is_blocked else 0, user_id),
            )
            conn.commit()

    await asyncio.to_thread(_set_block)


async def is_user_blocked(user_id: int) -> bool:
    def _is_blocked() -> bool:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return bool(row.get("is_blocked", 0))
            return False

    return await asyncio.to_thread(_is_blocked)


async def get_all_users() -> list[dict]:
    def _get_users() -> list[dict]:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
            return cursor.fetchall()

    return await asyncio.to_thread(_get_users)


async def get_bot_stats() -> dict:
    def _stats() -> dict:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total_users FROM users")
            total_users = cursor.fetchone()["total_users"]

            today_date = datetime.date.today().isoformat()
            cursor.execute(
                "SELECT COUNT(*) AS today_users FROM users WHERE date(created_at) = date('now')"
            )
            today_users = cursor.fetchone()["today_users"]

            cursor.execute("SELECT COUNT(*) AS total_movies FROM movies")
            total_movies = cursor.fetchone()["total_movies"]

            cursor.execute(
                """
                SELECT COUNT(*) AS premium_users FROM users
                WHERE premium_until IS NOT NULL AND premium_until > datetime('now')
                """
            )
            premium_users = cursor.fetchone()["premium_users"]

            cursor.execute(
                """
                SELECT title, code, views FROM movies
                ORDER BY views DESC LIMIT 5
                """
            )
            top_movies = cursor.fetchall()

            return {
                "total_users": total_users,
                "today_users": today_users,
                "total_movies": total_movies,
                "premium_users": premium_users,
                "top_movies": top_movies,
            }

    return await asyncio.to_thread(_stats)


async def get_channels() -> list[dict]:
    def _channels() -> list[dict]:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM channels ORDER BY id ASC")
            return cursor.fetchall()

    return await asyncio.to_thread(_channels)


async def add_channel(channel_id: str, title: str, invite_link: str) -> None:
    def _add() -> None:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO channels (channel_id, title, invite_link, created_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(channel_id) DO UPDATE SET
                    title = excluded.title,
                    invite_link = excluded.invite_link;
                """,
                (channel_id.strip(), title.strip(), invite_link.strip()),
            )
            conn.commit()

    await asyncio.to_thread(_add)


async def delete_channel(channel_id: str) -> None:
    def _delete() -> None:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id.strip(),))
            conn.commit()

    await asyncio.to_thread(_delete)


async def get_sub_required_setting() -> bool:
    def _get() -> bool:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'sub_required'")
            row = cursor.fetchone()
            if row:
                return row["value"] == "1"
            return True

    return await asyncio.to_thread(_get)


async def set_sub_required_setting(enabled: bool) -> None:
    def _set() -> None:
        with _get_connection() as conn:
            cursor = conn.cursor()
            val = "1" if enabled else "0"
            cursor.execute(
                """
                INSERT INTO settings (key, value)
                VALUES ('sub_required', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value;
                """,
                (val,),
            )
            conn.commit()

    await asyncio.to_thread(_set)