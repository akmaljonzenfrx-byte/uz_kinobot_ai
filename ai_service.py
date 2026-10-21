import json
import logging
import re
import httpx
from config import GROQ_API_KEY

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


async def find_movie_with_ai(user_prompt: str, movies_catalog: list[dict]) -> dict:
    """
    Groq AI yordamida foydalanuvchi matni bo'yicha katalogdagi eng mos kinoni topadi.
    Katalogda bo'lmagan kinolarni to'qib chiqarmaydi.
    
    Qaytariladigan lug'at shakli:
    {
        "found": bool,
        "exact_match": dict | None,
        "suggestions": list[dict],
        "reasoning": str
    }
    """
    if not movies_catalog:
        return {
            "found": False,
            "exact_match": None,
            "suggestions": [],
            "reasoning": "Katalogda hozircha biror ham kino yo'q."
        }

    catalog_summary = []
    movie_by_code = {}
    for m in movies_catalog:
        code = str(m.get("code", "")).strip()
        movie_by_code[code] = m
        catalog_summary.append({
            "code": code,
            "title": m.get("title", ""),
            "year": m.get("year", 0),
            "genre": m.get("genre", ""),
            "description": m.get("description", "")
        })

    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY topilmadi, kalit so'zlar bo'yicha zaxira qidiruv ishlatilmoqda.")
        return _fallback_keyword_search(user_prompt, movies_catalog)

    system_prompt = (
        "Siz professional kinolar bo'yicha sun'iy intellekt yordamchisiz. "
        "Sizga foydalanuvchi tavsifi va bazadagi mavjud kinolar katalogi beriladi.\n"
        "VAZIFA:\n"
        "1. Foydalanuvchi so'ragan/tasvirlagan filmni SHUNDAY va FAQAT berilgan katalog ichidan toping.\n"
        "2. KATALOGDA YO'Q FILMLARNI HECH QACHON TO'QIB CHIQARMANG!\n"
        "3. Agar katalogdagi filmlardan biri foydalanuvchi so'roviga aniq yoki juda yaqin mos kelsa, "
        "\"found\": true va uning \"matched_code\" qiymatini belgilang.\n"
        "4. Agar aniq mos keladigan film topilmasa, \"found\": false deb belgilang va 3 tagacha eng yaqin "
        "variantlarning kodlarini \"suggestion_codes\" ro'yxatiga kiriting.\n"
        "5. Javobingizni FAQAT va FAQAT to'g'ri JSON formatida qaytaring, boshqa matn yozmang.\n\n"
        "Javob JSON formati shakli:\n"
        "{\n"
        "  \"found\": true/false,\n"
        "  \"matched_code\": \"kino_kodi\" yoki null,\n"
        "  \"suggestion_codes\": [\"kod1\", \"kod2\"],\n"
        "  \"reasoning\": \"Nima uchun bu film tanlangani haqida qisqa o'zbekcha izoh\"\n"
        "}"
    )

    user_content = json.dumps({
        "user_query": user_prompt,
        "catalog": catalog_summary
    }, ensure_ascii=False)

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(GROQ_API_URL, json=payload, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Groq API xatosi ({response.status_code}): {response.text}")
                return _fallback_keyword_search(user_prompt, movies_catalog)

            res_json = response.json()
            ai_content = res_json["choices"][0]["message"]["content"]
            parsed_res = json.loads(ai_content)

            found = parsed_res.get("found", False)
            matched_code = parsed_res.get("matched_code")
            suggestion_codes = parsed_res.get("suggestion_codes", [])
            reasoning = parsed_res.get("reasoning", "")

            exact_match = movie_by_code.get(str(matched_code)) if matched_code else None
            
            if found and not exact_match:
                found = False

            suggestions = []
            for sc in suggestion_codes:
                sc_str = str(sc)
                if sc_str in movie_by_code and (not exact_match or movie_by_code[sc_str]["id"] != exact_match["id"]):
                    if movie_by_code[sc_str] not in suggestions:
                        suggestions.append(movie_by_code[sc_str])
                if len(suggestions) >= 3:
                    break

            return {
                "found": found,
                "exact_match": exact_match,
                "suggestions": suggestions,
                "reasoning": reasoning
            }

    except Exception as e:
        logger.exception(f"AI qidiruvida xatolik yuz berdi: {e}")
        return _fallback_keyword_search(user_prompt, movies_catalog)


def _fallback_keyword_search(user_prompt: str, movies_catalog: list[dict]) -> dict:
    """Groq API ishlamaganda yoki kalit mavjud bo'lmaganda ishlovchi sodda zaxira qidiruvi."""
    words = set(re.findall(r'\w+', user_prompt.lower()))
    if not words:
        return {
            "found": False,
            "exact_match": None,
            "suggestions": [],
            "reasoning": "Qidiruv matni yetarli emas."
        }

    scored_movies = []
    for movie in movies_catalog:
        text = f"{movie.get('title', '')} {movie.get('genre', '')} {movie.get('description', '')}".lower()
        score = sum(1 for word in words if word in text)
        if score > 0:
            scored_movies.append((score, movie))

    scored_movies.sort(key=lambda x: x[0], reverse=True)

    if not scored_movies:
        return {
            "found": False,
            "exact_match": None,
            "suggestions": [],
            "reasoning": "Siz izlagan tavsifga mos keladigan hech qanday kino topilmadi."
        }

    top_score, top_movie = scored_movies[0]
    if top_score >= 2 or len(words) == 1:
        suggestions = [m for s, m in scored_movies[1:4]]
        return {
            "found": True,
            "exact_match": top_movie,
            "suggestions": suggestions,
            "reasoning": "Kalit so'zlar bo'yicha eng mos keluvchi kino topildi."
        }
    else:
        suggestions = [m for s, m in scored_movies[:3]]
        return {
            "found": False,
            "exact_match": None,
            "suggestions": suggestions,
            "reasoning": "Aniq moslik topilmadi, lekin ushbu filmlar yaqin bo'lishi mumkin."
        }