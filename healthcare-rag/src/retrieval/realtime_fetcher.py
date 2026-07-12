"""
src/retrieval/realtime_fetcher.py
───────────────────────────────────
Fetch nội dung real-time từ các nguồn y tế đáng tin cậy.

Dùng Redis đã có trong project (cùng REDIS_URL với session.py),
không tạo thêm connection mới.

Mỗi URL được cache 24h — không bao giờ fetch lại nếu cache còn sống.
"""
from __future__ import annotations

import hashlib
import os
from typing import Optional

import httpx
import trafilatura
from loguru import logger

# Dùng cùng REDIS_URL với src/rag/session.py
_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
_WEB_TTL   = 86400   # 24h

# ── Mapping keyword → URL đáng tin cậy ───────────────────────
# Chỉ dùng nguồn public domain / không block bot
TRUSTED_URLS: dict[str, str] = {
    "hba1c":         "https://www.cdc.gov/diabetes/managing/managing-blood-sugar/a1c.html",
    "blood_glucose": "https://www.cdc.gov/diabetes/managing/managing-blood-sugar/bloodglucose.html",
    "prevention":    "https://www.cdc.gov/diabetes/prevention/index.html",
    "type1":         "https://www.cdc.gov/diabetes/basics/type1.html",
    "type2":         "https://www.cdc.gov/diabetes/basics/type2.html",
    "symptoms":      "https://www.cdc.gov/diabetes/basics/symptoms.html",
    "testing":       "https://www.cdc.gov/diabetes/basics/getting-tested.html",
    "complications": "https://www.cdc.gov/diabetes/complications/index.html",
    "foot_care":     "https://www.cdc.gov/diabetes/complications/foot.html",
    "kidney":        "https://www.cdc.gov/diabetes/complications/kidney.html",
    "heart":         "https://www.cdc.gov/diabetes/complications/heart.html",
    "eye":           "https://www.cdc.gov/diabetes/complications/eye.html",
    "nerve":         "https://www.cdc.gov/diabetes/complications/nerve.html",
    "eating":        "https://www.cdc.gov/diabetes/managing/eat-well/index.html",
    "exercise":      "https://www.cdc.gov/diabetes/managing/be-active.html",
    "who_fact":      "https://www.who.int/news-room/fact-sheets/detail/diabetes",
}

# Keyword (chuỗi không dấu) → key trong TRUSTED_URLS
KEYWORD_MAP: list[tuple[tuple[str, ...], str]] = [
    (("hba1c", "a1c", "hemoglobin"),                      "hba1c"),
    (("duong huyet", "blood sugar", "glucose", "mg/dl"),  "blood_glucose"),
    (("phong ngua", "tien tieu duong", "prediabetes"),    "prevention"),
    (("type 1", "type1", "t1d", "tuype 1"),               "type1"),
    (("type 2", "type2", "t2d", "tuype 2"),               "type2"),
    (("trieu chung", "dau hieu", "symptom"),              "symptoms"),
    (("xet nghiem", "chan doan", "test", "diagnos"),      "testing"),
    (("bien chung", "complication"),                      "complications"),
    (("ban chan", "foot", "loet"),                        "foot_care"),
    (("than", "kidney", "nephropathy", "ckd"),            "kidney"),
    (("tim mach", "heart", "cardiovascular"),             "heart"),
    (("mat", "vong mac", "eye", "retinopathy"),           "eye"),
    (("than kinh", "te bi", "nerve", "neuropathy"),       "nerve"),
    (("an uong", "che do an", "thuc pham", "eat", "diet"),"eating"),
    (("the duc", "van dong", "exercise", "tap luyen"),    "exercise"),
    (("who", "the gioi", "toan cau", "global"),           "who_fact"),
]


def _norm(text: str) -> str:
    """Bỏ dấu tiếng Việt — dùng lại logic từ retriever.py."""
    import unicodedata
    text = text.replace("đ", "d").replace("Đ", "D")
    lowered = text.lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(c) != "Mn"
    )


def _find_url(query: str) -> Optional[str]:
    q = _norm(query)
    for keywords, url_key in KEYWORD_MAP:
        if any(kw in q for kw in keywords):
            url = TRUSTED_URLS.get(url_key)
            logger.debug(f"realtime_fetcher: mapped '{url_key}' → {url}")
            return url
    return None


def _get_redis():
    try:
        import redis
        r = redis.from_url(
            _REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
        )
        r.ping()
        return r
    except Exception:
        return None


def _cache_key(url: str) -> str:
    return f"rag:web:{hashlib.md5(url.encode()).hexdigest()[:10]}"


async def fetch_realtime_context(query: str) -> Optional[str]:
    """
    Tìm URL phù hợp với câu hỏi → cache check → fetch nếu miss.

    Returns:
        Text content (~3000 chars) hoặc None nếu không tìm thấy/lỗi.
    """
    url = _find_url(query)
    if not url:
        logger.debug("realtime_fetcher: không tìm được URL phù hợp")
        return None

    r = _get_redis()
    key = _cache_key(url)

    # Cache hit
    if r:
        try:
            cached = r.get(key)
            if cached:
                logger.debug(f"🌐 Web cache HIT ({len(cached)} chars): {url}")
                return cached
        except Exception:
            pass

    # Fetch
    logger.info(f"🌐 Fetching: {url}")
    try:
        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            headers={"User-Agent": "DiabetesRAGBot/1.0 (+healthcare-rag)"},
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(f"Web fetch {resp.status_code}: {url}")
                return None

        text = trafilatura.extract(
            resp.text,
            url=url,
            include_tables=True,
            include_links=False,
            favor_recall=True,
            no_fallback=False,
        )

        if not text or len(text) < 150:
            logger.warning(f"Nội dung quá ngắn hoặc rỗng: {url}")
            return None

        content = text[:3000]

        # Lưu cache
        if r:
            try:
                r.setex(key, _WEB_TTL, content)
            except Exception:
                pass

        logger.info(f"✅ Web fetch OK ({len(content)} chars): {url}")
        return content

    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching: {url}")
        return None
    except Exception as e:
        logger.warning(f"Web fetch lỗi {url}: {e}")
        return None
