"""
src/llm/gemini_client.py
─────────────────────────
GeminiKeyPool + HTTP client.

Tách hoàn toàn khỏi RAG logic:
  - Quản lý API key xoay vòng (429 → next key)
  - Retry + exponential backoff
  - Fallback model chain
  - Không biết gì về prompt / context / retrieval
"""
from __future__ import annotations

import random
import threading
import time
from typing import Dict, List, Optional

import requests
from loguru import logger

from src.utils.config import cfg

# ── Config ─────────────────────────────────────────────────────
_LLM_TIMEOUT    = cfg.llm.timeout_s
_MAX_RETRIES    = cfg.llm.max_retries
_BASE_DELAY     = cfg.llm.retry_base_delay
_MAX_DELAY      = cfg.llm.retry_max_delay
_API_BASE       = cfg.llm.api_base
_THINKING       = cfg.llm.thinking_budget
_RETRY_CODES    = {408, 409, 429, 500, 502, 503, 504}


# ================================================================
# Custom Exception
# ================================================================

class LLMAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


# ================================================================
# Key Pool
# ================================================================

class GeminiKeyPool:
    """
    Quản lý nhiều Gemini API key, tự xoay khi hết quota (429).

    Key được đọc từ env: GEMINI_API_KEY_1 … GEMINI_API_KEY_19
    Fallback: GEMINI_API_KEY hoặc GOOGLE_API_KEY
    """

    COOLDOWN_S = 3_600  # 1 giờ

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
        import os
        keys: list[str] = []
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

    def current_key(self) -> str:
        with self._lock:
            now = time.time()
            for i in range(len(self._keys)):
                idx = (self._index + i) % len(self._keys)
                if now >= self._cooldown_until.get(self._keys[idx], 0):
                    self._index = idx
                    return self._keys[idx]
            # Tất cả key đang cooldown → dùng key ít chờ nhất
            best = min(self._keys, key=lambda k: self._cooldown_until.get(k, 0))
            wait = max(0, self._cooldown_until[best] - now)
            logger.warning(f"⚠ Tất cả key cooldown. Key tốt nhất còn {wait:.0f}s")
            return best

    def mark_exhausted(self, key: str) -> None:
        with self._lock:
            self._cooldown_until[key] = time.time() + self.COOLDOWN_S
            self._index = (self._index + 1) % len(self._keys)
            logger.warning(f"🔄 Key hết quota (429) → chuyển sang key #{self._index + 1}")

    def rotate_after_error(self, key: str) -> None:
        """Đổi sang key kế tiếp cho lỗi tạm thời/timeout, không cooldown key hiện tại."""
        with self._lock:
            try:
                current = self._keys.index(key)
            except ValueError:
                self._index = (self._index + 1) % len(self._keys)
            else:
                self._index = (current + 1) % len(self._keys)
            logger.warning(f"🔄 LLM chậm/lỗi tạm thời → thử Gemini key #{self._index + 1}")

    @property
    def key_count(self) -> int:
        return len(self._keys)


# ================================================================
# HTTP Client
# ================================================================

def _retry_delay(attempt: int) -> float:
    backoff = _BASE_DELAY * (2 ** max(attempt - 1, 0))
    return min(backoff + random.uniform(0, 0.5), _MAX_DELAY)


def _dedupe(models: List[str]) -> List[str]:
    seen, out = set(), []
    for m in models:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


_HARD_PROMPT_KEYWORDS = (
    "so sánh", "phân biệt", "khác nhau", "khác biệt", "điều trị", "phác đồ",
    "liều", "tác dụng phụ", "chống chỉ định", "cơ chế", "biến chứng",
    "nguy cơ", "theo dõi", "hướng dẫn", "quy trình", "tổng hợp",
)


def _flatten_prompt(contents: List[Dict], system_prompt: Optional[str]) -> str:
    parts: List[str] = []
    if system_prompt:
        parts.append(system_prompt)
    for item in contents or []:
        if not isinstance(item, dict):
            continue
        for part in item.get("parts", []) or []:
            if isinstance(part, dict):
                text = part.get("text")
                if text:
                    parts.append(text)
    return "\n".join(parts)


def _prefer_primary_model(prompt_text: str, max_tokens: int) -> bool:
    normalized = f" {prompt_text.lower()} "
    if len(prompt_text) >= 1800:
        return True
    if max_tokens and max_tokens >= 2600:
        return True
    return any(keyword in normalized for keyword in _HARD_PROMPT_KEYWORDS)


class GeminiClient:
    """
    Gửi request tới Gemini API với:
      - Key rotation (GeminiKeyPool)
      - Retry + backoff
      - Model fallback chain
    """

    def __init__(self, key_pool: Optional[GeminiKeyPool] = None):
        self.key_pool = key_pool or GeminiKeyPool()
        primary = cfg.llm.model
        fallbacks = cfg.llm.fallback_models
        self.model_chain = _dedupe([primary, *fallbacks])
        logger.info(f"🤖 Gemini models: {self.model_chain}")

    def _url(self, model: str) -> str:
        return f"{_API_BASE}/models/{model}:generateContent"

    def generate(
        self,
        contents: List[Dict],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict:
        """
        Gọi Gemini generateContent.

        Args:
            contents:      Gemini contents list (role + parts)
            system_prompt: System instruction text
            max_tokens:    Override max output tokens
            temperature:   Override temperature

        Returns:
            Gemini JSON response dict

        Raises:
            LLMAPIError
        """
        payload: Dict = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens or cfg.llm.max_tokens,
                "temperature":     temperature if temperature is not None else cfg.llm.temperature,
                "thinkingConfig":  {"thinkingBudget": _THINKING},
            },
        }
        if system_prompt:
            payload["system_instruction"] = {"parts": [{"text": system_prompt}]}

        prompt_text = _flatten_prompt(contents, system_prompt)
        model_chain = self.model_chain if _prefer_primary_model(
            prompt_text,
            max_tokens or cfg.llm.max_tokens,
        ) else _dedupe([*(self.model_chain[1:]), self.model_chain[0]])

        last_error: Optional[LLMAPIError] = None

        for model in model_chain:
            if model != model_chain[0]:
                logger.warning(f"  Fallback → {model}")

            max_attempts = min(_MAX_RETRIES + 1, max(self.key_pool.key_count, 1))
            for attempt in range(1, max_attempts + 1):
                key = self.key_pool.current_key()
                headers = {
                    "x-goog-api-key": key,
                    "Content-Type": "application/json",
                }
                try:
                    resp = requests.post(
                        self._url(model),
                        headers=headers,
                        json=payload,
                        timeout=_LLM_TIMEOUT,
                    )
                except requests.RequestException as exc:
                    last_error = LLMAPIError(str(exc), retryable=True)
                    self.key_pool.rotate_after_error(key)
                else:
                    if resp.ok:
                        return resp.json()

                    if resp.status_code == 429:
                        self.key_pool.mark_exhausted(key)
                    elif resp.status_code in _RETRY_CODES:
                        self.key_pool.rotate_after_error(key)

                    retryable = resp.status_code in _RETRY_CODES
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

                if attempt < max_attempts:
                    delay = 0.2 if self.key_pool.key_count > 1 else _retry_delay(attempt)
                    logger.warning(f"  Retry LLM key {attempt}/{max_attempts - 1} sau {delay:.1f}s")
                    time.sleep(delay)

        raise last_error or LLMAPIError("Không có model nào khả dụng")

    @staticmethod
    def extract_text(response: Dict) -> str:
        """Trích text từ Gemini response JSON."""
        candidates = response.get("candidates") or []
        if not candidates:
            raise LLMAPIError("Gemini không trả về candidate")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if p.get("text"))
        if not text:
            reason = candidates[0].get("finishReason", "unknown")
            raise LLMAPIError(f"Gemini không trả về text. finishReason={reason}")

        # Cảnh báo khi response bị cắt cụt do hết maxOutputTokens — trước đây
        # lỗi này "âm thầm" (text vẫn non-empty nên không raise), khiến người
        # dùng nhận câu trả lời bị ngắt giữa câu mà không ai biết tại sao.
        finish_reason = candidates[0].get("finishReason", "")
        if finish_reason == "MAX_TOKENS":
            logger.warning(
                f"⚠ Response bị CẮT CỤT do hết maxOutputTokens! "
                f"({len(text)} ký tự). Tăng max_tokens cho query này."
            )

        return text
