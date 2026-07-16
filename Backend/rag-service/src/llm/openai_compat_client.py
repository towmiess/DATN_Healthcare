"""
src/llm/openai_compat_client.py
─────────────────────────────────
Client dùng chung cho mọi API theo chuẩn OpenAI Chat Completions:
  - OpenAI       (api.openai.com/v1)
  - xAI Grok     (api.x.ai/v1)          ← cùng format request/response với OpenAI

Mục đích: tách riêng 1 provider cho route DRUG (tra cứu thuốc realtime),
để không bị tắc nghẽn / cạn quota chung với Gemini (dùng cho các route khác).
Cùng interface .generate()/.extract_text() như GeminiClient nên pipeline.py
có thể dùng thay thế cho nhau mà không cần đổi code gọi.

Cấu hình qua .env:
  DRUG_LLM_PROVIDER=grok            # "grok" | "openai" | "" (tắt, dùng Gemini)
  GROK_API_KEY=xai-...
  GROK_MODEL=grok-4-fast
  OPENAI_API_KEY=sk-...
  OPENAI_MODEL=gpt-4o-mini
"""
from __future__ import annotations

import os
import random
import time
from typing import Dict, List, Optional

import requests
from loguru import logger

from src.utils.config import cfg

_RETRY_CODES = {408, 409, 429, 500, 502, 503, 504}

PROVIDER_CONFIG = {
    "grok": {
        "base_url": "https://api.x.ai/v1",
        "api_key_env": "GROK_API_KEY",
        "model_env":   "GROK_MODEL",
        "default_model": "grok-4-fast",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "model_env":   "OPENAI_MODEL",
        "default_model": "gpt-4o-mini",
    },
}


class LLMAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def _gemini_contents_to_messages(
    contents: List[Dict], system_prompt: Optional[str] = None
) -> List[Dict]:
    """
    Pipeline hiện build `contents` theo format Gemini:
        [{"role": "user", "parts": [{"text": "..."}]}]
    Hàm này convert sang format OpenAI:
        [{"role": "user", "content": "..."}]
    để dùng chung 1 interface .generate(contents, ...) cho mọi provider.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for c in contents:
        role = c.get("role", "user")
        role = "assistant" if role == "model" else role
        text = "".join(p.get("text", "") for p in c.get("parts", []))
        messages.append({"role": role, "content": text})
    return messages


class OpenAICompatClient:
    """
    Gọi bất kỳ API nào theo chuẩn OpenAI Chat Completions (OpenAI / Grok).
    Có retry + backoff, KHÔNG có key-pool nhiều key (1 key/provider là đủ
    cho route DRUG vì lưu lượng thấp hơn nhiều so với route chính).
    """

    def __init__(self, provider: str):
        provider = provider.lower().strip()
        if provider not in PROVIDER_CONFIG:
            raise ValueError(f"Provider không hỗ trợ: '{provider}' (chỉ 'grok' hoặc 'openai')")

        cfg = PROVIDER_CONFIG[provider]
        self.provider  = provider
        self.base_url  = cfg["base_url"]
        self.api_key   = os.getenv(cfg["api_key_env"], "").strip()
        self.model     = os.getenv(cfg["model_env"], "").strip() or cfg["default_model"]

        if not self.api_key:
            raise ValueError(
                f"Thiếu {cfg['api_key_env']} trong .env cho provider '{provider}'"
            )
        logger.info(f"🤖 OpenAICompatClient sẵn sàng: provider={provider} model={self.model}")

    def generate(
        self,
        contents: List[Dict],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        max_retries: Optional[int] = None,
        timeout_s: Optional[int] = None,
    ) -> Dict:
        messages = _gemini_contents_to_messages(contents, system_prompt)
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or 1024,
            "temperature": temperature if temperature is not None else 0.1,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Optional[LLMAPIError] = None
        effective_retries = max_retries if max_retries is not None else cfg.llm.max_retries
        effective_timeout = timeout_s if timeout_s is not None else cfg.llm.timeout_s
        for attempt in range(1, effective_retries + 2):
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=effective_timeout,
                )
            except requests.RequestException as exc:
                last_error = LLMAPIError(str(exc), retryable=True)
            else:
                if resp.ok:
                    return resp.json()

                retryable = resp.status_code in _RETRY_CODES
                try:
                    msg = resp.json().get("error", {}).get("message", resp.text)
                except Exception:
                    msg = resp.text
                last_error = LLMAPIError(
                    f"{self.provider} {resp.status_code}: {msg}",
                    status_code=resp.status_code,
                    retryable=retryable,
                )
                if not retryable:
                    raise last_error

            if attempt <= effective_retries:
                delay = min(1.0 * (2 ** (attempt - 1)) + random.uniform(0, 0.5), 8.0)
                logger.warning(f"  [{self.provider}] Retry {attempt}/{effective_retries} sau {delay:.1f}s")
                time.sleep(delay)

        raise last_error or LLMAPIError(f"{self.provider}: không có phản hồi")

    @staticmethod
    def extract_text(response: Dict) -> str:
        choices = response.get("choices") or []
        if not choices:
            raise LLMAPIError("Không có choices trong phản hồi")
        msg = choices[0].get("message", {})
        text = msg.get("content", "")
        if not text:
            reason = choices[0].get("finish_reason", "unknown")
            raise LLMAPIError(f"Không có text trong phản hồi. finish_reason={reason}")

        if choices[0].get("finish_reason") == "length":
            logger.warning(
                f"⚠ Response bị CẮT CỤT do hết max_tokens! ({len(text)} ký tự)."
            )
        return text


class MultiLLMClient:
    """
    Bọc nhiều OpenAICompatClient (vd: Grok + OpenAI), thử lần lượt theo thứ
    tự ưu tiên. Nếu provider đầu lỗi/hết quota/bị rate-limit → tự chuyển
    sang provider kế tiếp ngay trong cùng 1 request, KHÔNG cần đợi người
    dùng hỏi lại. Đây là lớp "không bị tắc nghẽn" thật sự — vì có ≥2 nguồn
    độc lập cho riêng route DRUG, tách khỏi quota của Gemini.
    """

    def __init__(self, clients: List["OpenAICompatClient"]):
        self.clients  = clients
        self.provider = "+".join(c.provider for c in clients)  # vd: "grok+openai"

    def generate(self, contents, system_prompt=None, max_tokens=None, **kw) -> Dict:
        last_err = None
        for c in self.clients:
            try:
                return c.generate(contents, system_prompt=system_prompt, max_tokens=max_tokens, **kw)
            except Exception as e:
                logger.warning(f"[MultiLLM] {c.provider} lỗi: {e} → thử provider kế tiếp")
                last_err = e
        raise last_err or LLMAPIError("Tất cả provider trong MultiLLMClient đều lỗi")

    @staticmethod
    def extract_text(response: Dict) -> str:
        # Grok và OpenAI trả cùng format Chat Completions → dùng chung 1 parser
        return OpenAICompatClient.extract_text(response)


def build_drug_llm_client():
    """
    Tạo client riêng cho route DRUG, đọc danh sách provider từ env
    DRUG_LLM_PROVIDERS (phân tách bằng dấu phẩy, thứ tự = thứ tự ưu tiên/
    fallback). Hỗ trợ dùng CẢ Grok và OpenAI cùng lúc:

        DRUG_LLM_PROVIDERS=grok,openai

    → Ưu tiên Grok; nếu Grok lỗi/hết quota/rate-limit ngay trong request đó,
    tự chuyển sang OpenAI mà không làm fail cả câu trả lời. Nếu cả 2 đều
    lỗi, pipeline.py sẽ tự fallback tiếp sang Gemini (lớp an toàn cuối).

    Vẫn nhận biến cũ DRUG_LLM_PROVIDER (số ít, 1 provider) để tương thích
    ngược nếu bạn chỉ muốn dùng 1 trong 2.

    Trả về None nếu không cấu hình gì → route DRUG dùng chung Gemini.
    """
    raw = os.getenv("DRUG_LLM_PROVIDERS", "").strip()
    if not raw:
        raw = os.getenv("DRUG_LLM_PROVIDER", "").strip()   # backward-compat

    providers = [p.strip().lower() for p in raw.split(",") if p.strip()]
    if not providers:
        logger.info("DRUG_LLM_PROVIDERS chưa cấu hình → route DRUG dùng chung Gemini")
        return None

    clients = []
    for p in providers:
        try:
            clients.append(OpenAICompatClient(p))
        except ValueError as e:
            logger.warning(f"⚠ Bỏ qua provider '{p}' cho drug LLM: {e}")

    if not clients:
        logger.warning("⚠ Không khởi tạo được provider nào cho drug LLM → fallback Gemini")
        return None
    if len(clients) == 1:
        return clients[0]

    logger.success(f"🤖 Drug LLM dùng {len(clients)} provider (chain): "
                    f"{' → '.join(c.provider for c in clients)}")
    return MultiLLMClient(clients)
