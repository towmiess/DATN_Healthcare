"""
================================================================
RAG PIPELINE — Retrieve → Augment → Generate
================================================================

Cải tiến so với v1:
  - Vector DB: Qdrant (thay ChromaDB)
  - Session: Redis (thay in-memory)
  - LLM key: GeminiKeyPool (tự xoay khi 429)
  - Cache: RAGCache (câu hỏi lặp trả lời ngay)
  - Intent: thêm biến chứng (cardiovascular, nephropathy, ...)
================================================================
"""

import os
import sys
import re
import json
import time
import random
import hashlib
import threading
import unicodedata
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger
from dotenv import load_dotenv

import requests

load_dotenv()

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.rag.indexer import VectorIndexer, USER_RESPONSE_RULE_CATEGORY

# ── Cấu hình ────────────────────────────────────────────────
_configured_model    = os.getenv("LLM_MODEL", "gemini-2.0-flash-lite")
LLM_MODEL            = _configured_model
MAX_TOKENS           = int(os.getenv("MAX_TOKENS", 1024))
TOP_K                = int(os.getenv("RAG_TOP_K", 4))
LLM_TEMPERATURE      = float(os.getenv("LLM_TEMPERATURE", 0.1))
LLM_TIMEOUT          = int(os.getenv("LLM_TIMEOUT", 60))
LLM_MAX_RETRIES      = int(os.getenv("LLM_MAX_RETRIES", 2))
LLM_RETRY_BASE_DELAY = float(os.getenv("LLM_RETRY_BASE_DELAY", 1.0))
LLM_RETRY_MAX_DELAY  = float(os.getenv("LLM_RETRY_MAX_DELAY", 8.0))
GEMINI_API_BASE      = os.getenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta")
GEMINI_THINKING_BUDGET = int(os.getenv("GEMINI_THINKING_BUDGET", 0))
GEMINI_FALLBACK_MODELS = [
    m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash").split(",") if m.strip()
]
GEMINI_RETRY_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}

USER_KNOWLEDGE_ENABLED   = os.getenv("USER_KNOWLEDGE_ENABLED", "false").lower() not in {"0", "false", "no"}
USER_KNOWLEDGE_MIN_CHARS = int(os.getenv("USER_KNOWLEDGE_MIN_CHARS", 40))
USER_RULE_TOP_K          = int(os.getenv("USER_RULE_TOP_K", 3))
USER_RULE_MIN_SIMILARITY = float(os.getenv("USER_RULE_MIN_SIMILARITY", 0.18))


INTENT_CATEGORY_FILTERS = {
    "emergency":     ["emergency", "blood_glucose"],
    "medication":    ["medication", "blood_glucose"],
    "diet":          ["diet", "lifestyle"],
    "blood_glucose": ["blood_glucose", "emergency"],
    "complication": [
        "complication", "cardiovascular", "nephropathy",
        "retinopathy", "neuropathy", "foot_care",
        "diagnosis", "general",
    ],
    "cardiovascular": ["cardiovascular", "complication", "general"],
    "nephropathy":    ["nephropathy", "complication", "general"],
    "retinopathy":    ["retinopathy", "complication", "general"],
    "neuropathy":     ["neuropathy", "complication", "foot_care", "general"],
    "foot_care":      ["foot_care", "neuropathy", "complication", "general"],
    "diagnosis":      ["diagnosis", "general"],
    "general":        ["general", "diagnosis", "lifestyle"],
}

SYSTEM_PROMPT = """Bạn là trợ lý y tế chuyên về bệnh tiểu đường (đái tháo đường).

Nhiệm vụ: Tư vấn dựa trên tài liệu y khoa được cung cấp.
Nguyên tắc:
- Chỉ trả lời dựa trên tài liệu tham khảo
- Luôn khuyên tham khảo bác sĩ cho quyết định điều trị
- Ưu tiên tài liệu đã xác minh bởi bác sĩ
- Trả lời bằng ngôn ngữ của câu hỏi (Việt/Anh)
- TUYỆT ĐỐI không bịa đặt thông tin y tế"""


# ================================================================
# GEMINI KEY POOL — Xoay API key khi 429
# ================================================================

class GeminiKeyPool:
    """Quản lý nhiều Gemini API key, tự xoay khi hết quota (429)."""

    COOLDOWN = 3600  # 1 giờ

    def __init__(self):
        self._keys = self._load_keys()
        self._index = 0
        self._cooldown_until: Dict[str, float] = {}
        self._lock = threading.Lock()

        if not self._keys:
            raise ValueError(
                "Không tìm thấy GEMINI_API_KEY!\n"
                "Thêm vào .env: GEMINI_API_KEY_1=AIza..."
            )
        logger.info(f"🔑 GeminiKeyPool: {len(self._keys)} key(s) sẵn sàng")

    def _load_keys(self) -> List[str]:
        keys = []
        for i in range(1, 20):
            k = os.getenv(f"GEMINI_API_KEY_{i}", "").strip()
            if k and not k.lower().startswith(("xxx", "your_", "your-")):
                keys.append(k)
        if not keys:
            for env in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                k = os.getenv(env, "").strip()
                if k and not k.lower().startswith(("xxx", "your_", "your-")):
                    keys.append(k)
                    break
        return keys

    def _available(self, key: str) -> bool:
        return time.time() >= self._cooldown_until.get(key, 0)

    def current_key(self) -> str:
        with self._lock:
            for i in range(len(self._keys)):
                idx = (self._index + i) % len(self._keys)
                if self._available(self._keys[idx]):
                    self._index = idx
                    return self._keys[idx]
            best = min(self._keys, key=lambda k: self._cooldown_until.get(k, 0))
            remaining = max(0, self._cooldown_until.get(best, 0) - time.time())
            logger.warning(f"⚠ Tất cả key cooldown. Tốt nhất còn {remaining:.0f}s")
            return best

    def mark_exhausted(self, key: str) -> None:
        with self._lock:
            self._cooldown_until[key] = time.time() + self.COOLDOWN
            self._index = (self._index + 1) % len(self._keys)
            logger.warning(f"🔄 Key hết quota (429) → chuyển key #{self._index + 1}")


# ================================================================
# RESPONSE CACHE — Trả lời ngay cho câu hỏi lặp lại
# ================================================================

class RAGCache:
    def __init__(self, max_size: int = 200, ttl: int = 3600):
        self._cache: Dict[str, dict] = {}
        self._ts: Dict[str, float] = {}
        self.max_size = max_size
        self.ttl = ttl
        self._lock = threading.Lock()

    def make_key(self, query: str) -> str:
        return hashlib.md5(" ".join(query.lower().split()).encode()).hexdigest()

    def get(self, key: str) -> Optional[dict]:
        with self._lock:
            if key not in self._cache:
                return None
            if time.time() - self._ts[key] > self.ttl:
                del self._cache[key], self._ts[key]
                return None
            return self._cache[key]

    def set(self, key: str, value: dict) -> None:
        with self._lock:
            if len(self._cache) >= self.max_size:
                oldest = min(self._ts, key=self._ts.get)
                del self._cache[oldest], self._ts[oldest]
            self._cache[key] = value
            self._ts[key] = time.time()


# ================================================================
# INTENT DETECTION
# ================================================================

def _norm(text: str) -> str:
    lowered = text.lower()
    no_accent = "".join(
        c for c in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(c) != "Mn"
    )
    return f" {lowered} {no_accent} "


def detect_intent(query: str) -> str:
    q = _norm(query)
    keywords = {
        "emergency": [
            "ha duong huyet", "duong huyet thap", "ngat", "hon me",
            "run tay", "mo hoi lanh", "cap cuu", "duoi 70 mg",
        ],
        "medication": [
            "thuoc", "metformin", "insulin", "gliclazide", "lieu",
            "uong thuoc", "tac dung phu", "don thuoc",
        ],
        "diet": [
            "an", "uong", "thuc pham", "pho", "com", "bun",
            "carb", "tinh bot", "che do an", "dinh duong",
        ],
        "blood_glucose": [
            "duong huyet", "hba1c", "glucose", "mg/dl", "mmol",
            "do duong", "chi so", "sau an",
        ],
        "cardiovascular": [
            "tim mach", "dot quy", "nhoi mau", "tang huyet ap",
            "huyet ap", "cholesterol", "suy tim", "stroke",
        ],
        "nephropathy": [
            "suy than", "benh than", "loc mau", "creatinine",
            "microalbumin", "gfr", "kidney", "ckd",
        ],
        "retinopathy": [
            "vong mac", "mo mat", "thi luc", "kham mat",
            "retinopathy", "mat bi mo",
        ],
        "neuropathy": [
            "te bi", "kho chan", "mat cam giac", "dau than kinh",
            "neuropathy", "numbness",
        ],
        "foot_care": [
            "ban chan", "loet chan", "vet loet", "mong chan",
            "foot ulcer", "diabetic foot",
        ],
        "complication": [
            "bien chung", "than", "mat", "vong mac", "tim mach",
            "complication",
        ],
        "diagnosis": [
            "chan doan", "phan loai", "type 1", "type 2",
            "tien tieu duong", "test", "xet nghiem",
        ],
    }
    for intent, kws in keywords.items():
        if any(kw in q for kw in kws):
            return intent
    return "general"


# ================================================================
# EMERGENCY SHORTCUTS
# ================================================================

_EMERGENCY_KWS = [
    "ha duong huyet", "duong huyet thap", "ngat xiu", "hon me",
    "co giat", "cap cuu", "52 mg", "50 mg", "duoi 70",
]

def _is_emergency(query: str) -> bool:
    q = _norm(query)
    return any(kw in q for kw in _EMERGENCY_KWS)


def _emergency_response(query: str) -> Dict:
    return {
        "query": query,
        "response": (
            "🚨 **KHẨN CẤP — Hạ Đường Huyết**\n\n"
            "**Xử lý ngay (Quy tắc 15-15):**\n"
            "1. Uống/ăn 15g carbs nhanh: 4 viên glucose, ½ ly nước ngọt, 1 muỗng mật ong\n"
            "2. Nghỉ ngơi 15 phút\n"
            "3. Đo đường huyết lại\n"
            "4. Nếu vẫn < 70 mg/dL → lặp lại bước 1\n"
            "5. Nếu mất ý thức → **Gọi 115 ngay**\n\n"
            "⚠ Không để một mình. Thông báo người thân ngay."
        ),
        "sources": [],
        "chunks_used": 0,
        "emergency": True,
    }


# ================================================================
# GEMINI API HELPERS
# ================================================================

class LLMAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def _dedupe_models(models: List[str]) -> List[str]:
    seen, result = set(), []
    for m in models:
        if m and m not in seen:
            seen.add(m)
            result.append(m)
    return result


def _retry_delay(attempt: int) -> float:
    backoff = LLM_RETRY_BASE_DELAY * (2 ** max(attempt - 1, 0))
    jitter = random.uniform(0, 0.5)
    return min(backoff + jitter, LLM_RETRY_MAX_DELAY)


# ================================================================
# PROMPT BUILDER
# ================================================================

def build_rag_prompt(query: str, chunks: List[Dict]) -> str:
    if not chunks:
        context = "Không có tài liệu tham khảo liên quan."
    else:
        parts = []
        for i, c in enumerate(chunks, 1):
            src = c["metadata"].get("source", "unknown")
            cat = c["metadata"].get("category", "")
            parts.append(f"[Tài liệu {i}] ({src} | {cat})\n{c['text']}")
        context = "\n\n---\n\n".join(parts)

    return f"""## TÀI LIỆU THAM KHẢO

{context}

---

## CÂU HỎI

{query}

---

## YÊU CẦU TRẢ LỜI

Dựa vào tài liệu trên:
1. Trả lời rõ ràng, thực tế
2. Trích dẫn tài liệu nào bạn dùng (ví dụ: "Theo [Tài liệu 2]...")
3. Đưa lời khuyên cụ thể
4. Kết thúc bằng khuyến nghị tham khảo bác sĩ nếu cần"""


# ================================================================
# RAG PIPELINE
# ================================================================

class RAGPipeline:
    def __init__(self):
        self.key_pool = GeminiKeyPool()
        self.cache = RAGCache(max_size=200, ttl=3600)
        self.model_candidates = _dedupe_models([LLM_MODEL, *GEMINI_FALLBACK_MODELS])

        self.indexer = VectorIndexer()
        stats = self.indexer.get_stats()
        if stats["total_chunks"] == 0:
            raise RuntimeError(
                "Vector Database trống!\n"
                "Chạy: python scripts/ingest.py"
            )
        logger.success(
            f"🚀 RAG Pipeline sẵn sàng "
            f"({stats['total_chunks']} chunks, model={LLM_MODEL})"
        )

    def _generate_url(self, model: str) -> str:
        return f"{GEMINI_API_BASE}/models/{model}:generateContent"

    def _post_gemini(self, contents: List[Dict]) -> requests.Response:
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": MAX_TOKENS,
                "temperature": LLM_TEMPERATURE,
                "thinkingConfig": {"thinkingBudget": GEMINI_THINKING_BUDGET},
            },
        }

        last_error = None
        for model_idx, model in enumerate(self.model_candidates, 1):
            url = self._generate_url(model)
            if model != LLM_MODEL:
                logger.warning(f"Fallback → {model}")

            for attempt in range(1, LLM_MAX_RETRIES + 2):
                current_key = self.key_pool.current_key()
                headers = {
                    "x-goog-api-key": current_key,
                    "Content-Type": "application/json",
                }
                try:
                    resp = requests.post(url, headers=headers, json=payload, timeout=LLM_TIMEOUT)
                except requests.RequestException as e:
                    last_error = LLMAPIError(str(e), retryable=True)
                else:
                    if resp.ok:
                        return resp
                    if resp.status_code == 429:
                        self.key_pool.mark_exhausted(current_key)
                    retryable = resp.status_code in GEMINI_RETRY_STATUS_CODES
                    try:
                        msg = resp.json().get("error", {}).get("message", resp.text)
                    except Exception:
                        msg = resp.text
                    last_error = LLMAPIError(
                        f"Gemini {resp.status_code}: {msg}",
                        status_code=resp.status_code,
                        retryable=retryable,
                    )
                    if not retryable:
                        raise last_error

                if attempt <= LLM_MAX_RETRIES:
                    delay = _retry_delay(attempt)
                    logger.warning(f"Retry {attempt}/{LLM_MAX_RETRIES} sau {delay:.1f}s")
                    time.sleep(delay)

        raise last_error or LLMAPIError("Không có model nào khả dụng")

    def _extract_text(self, data: Dict) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMAPIError("Gemini không trả về candidate")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if p.get("text"))
        if not text:
            raise LLMAPIError(f"Gemini không trả về text. finishReason={candidates[0].get('finishReason')}")
        return text

    def retrieve(self, query: str, top_k: int = TOP_K) -> List[Dict]:
        intent = detect_intent(query)
        categories = INTENT_CATEGORY_FILTERS.get(intent, INTENT_CATEGORY_FILTERS["general"])
        candidate_k = max(top_k * 4, 12)

        # Thử search với category filter
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchAny
            category_filter_obj = Filter(
                must=[FieldCondition(key="category", match=MatchAny(any=categories))]
            )
            chunks = self.indexer.search(query, top_k=candidate_k, where_filter=category_filter_obj)
        except Exception:
            chunks = self.indexer.search(query, top_k=candidate_k)

        min_sim = 0.24 if intent in {"general", "diagnosis"} else 0.28
        filtered = [c for c in chunks if c["similarity"] >= min_sim] or chunks

        # Rerank: semantic score + source priority
        def score(c):
            sem = c["similarity"]
            prio = c["metadata"].get("source_priority", 4)
            prio_score = max(0, (6 - int(prio)) / 5)
            return 0.85 * sem + 0.15 * prio_score

        reranked = sorted(filtered, key=score, reverse=True)[:top_k]
        logger.debug(f"  Retrieve intent={intent}: {len(reranked)} chunks")
        return reranked

    def generate(self, query: str, chunks: List[Dict]) -> str:
        prompt = build_rag_prompt(query, chunks)
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        resp = self._post_gemini(contents)
        return self._extract_text(resp.json())

    def answer(self, query: str, top_k: int = TOP_K, patient_context: Optional[Dict] = None) -> Dict:
        logger.info(f"❓ Query: '{query[:60]}...' intent={detect_intent(query)}")

        # Emergency shortcut
        if _is_emergency(query):
            return _emergency_response(query)

        # Cache check
        cache_key = self.cache.make_key(query)
        if not patient_context:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug("⚡ Cache hit")
                return cached

        # Retrieve
        chunks = self.retrieve(query, top_k=top_k)

        # Generate
        response = self.generate(query, chunks)

        # Tổng hợp nguồn
        sources = []
        seen = set()
        for c in chunks:
            src = c["metadata"].get("source", "unknown")
            if src not in seen:
                seen.add(src)
                sources.append({
                    "source": src,
                    "category": c["metadata"].get("category", ""),
                    "similarity": c["similarity"],
                })

        result = {
            "query": query,
            "response": response,
            "sources": sources,
            "chunks_used": len(chunks),
        }

        if not patient_context:
            self.cache.set(cache_key, result)

        logger.success(f"✅ Trả lời xong ({len(chunks)} chunks, {len(sources)} nguồn)")
        return result

    def answer_with_history(
        self,
        messages: List[Dict],
        top_k: int = TOP_K,
        patient_context: Optional[Dict] = None,
    ) -> Dict:
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        if not last_user:
            return {"query": "", "response": "Không có câu hỏi.", "sources": [], "chunks_used": 0}

        if _is_emergency(last_user):
            return _emergency_response(last_user)

        chunks = self.retrieve(last_user, top_k=top_k)

        history_lines = [
            f"{'Người dùng' if m['role'] == 'user' else 'Trợ lý'}: {m['content']}"
            for m in messages
        ]
        prompt = (
            "## LỊCH SỬ HỘI THOẠI\n"
            + "\n".join(history_lines)
            + "\n\n---\n\n"
            + build_rag_prompt(last_user, chunks)
        )
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        resp = self._post_gemini(contents)
        response = self._extract_text(resp.json())

        return {
            "query": last_user,
            "response": response,
            "sources": [{"source": c["metadata"].get("source", "")} for c in chunks],
            "chunks_used": len(chunks),
        }
