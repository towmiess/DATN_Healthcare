"""
================================================================
BƯỚC 4: RAG PIPELINE — Trái Tim Của Hệ Thống
================================================================

RAG (Retrieval-Augmented Generation) hoạt động như sau:

  User hỏi: "Tôi bị tiểu đường type 2, sáng ăn bát phở, nên làm gì?"
       │
       ▼
  [RETRIEVE] Tìm trong ChromaDB những đoạn văn liên quan nhất
       │         → "chế độ ăn tiểu đường", "phở GI cao", ...
       ▼
  [AUGMENT]  Ghép context vào prompt:
             "Dựa vào tài liệu sau: [context] ... Trả lời: [câu hỏi]"
       │
       ▼
  [GENERATE] Gemini LLM sinh câu trả lời chính xác, có nguồn
       │
       ▼
  Câu trả lời thân thiện + trích dẫn nguồn

TẠI SAO TỐT HƠN LLM THUẦN TÚY?
  - LLM thuần: "Phở bình thường thôi" (hallucinate, sai)
  - RAG: Dựa vào tài liệu chuẩn → "Phở có GI cao, bạn nên..."

CÁCH CHẠY:
  python src/rag/pipeline.py
================================================================
"""

import os
import sys
import json
import random
import time
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

import requests
sys.path.append(str(Path(__file__).parent.parent.parent))
from src.rag.indexer import USER_RESPONSE_RULE_CATEGORY, VectorIndexer

# ── Cấu hình ────────────────────────────────────────────────
_configured_model       = os.getenv("LLM_MODEL", "gemini-2.5-flash")
LLM_MODEL               = "gemini-2.5-flash" if _configured_model.startswith("claude") else _configured_model
MAX_TOKENS              = int(os.getenv("MAX_TOKENS", 2048))
TOP_K                   = int(os.getenv("TOP_K_RESULTS", 5))
LLM_TEMPERATURE         = float(os.getenv("LLM_TEMPERATURE", 0.2))
LLM_TIMEOUT             = int(os.getenv("LLM_TIMEOUT", 120))
LLM_MAX_RETRIES         = int(os.getenv("LLM_MAX_RETRIES", 3))
LLM_RETRY_BASE_DELAY    = float(os.getenv("LLM_RETRY_BASE_DELAY", 1.0))
LLM_RETRY_MAX_DELAY     = float(os.getenv("LLM_RETRY_MAX_DELAY", 10.0))
USER_KNOWLEDGE_ENABLED  = os.getenv("USER_KNOWLEDGE_ENABLED", "true").lower() not in {"0", "false", "no"}
USER_KNOWLEDGE_MIN_CHARS = int(os.getenv("USER_KNOWLEDGE_MIN_CHARS", 40))
USER_RULE_TOP_K         = int(os.getenv("USER_RULE_TOP_K", 3))
USER_RULE_MIN_SIMILARITY = float(os.getenv("USER_RULE_MIN_SIMILARITY", 0.18))
USER_RULE_EXPANSION_MAX_CHARS = int(os.getenv("USER_RULE_EXPANSION_MAX_CHARS", 900))
GEMINI_API_BASE         = os.getenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta")
GEMINI_THINKING_BUDGET  = int(os.getenv("GEMINI_THINKING_BUDGET", 0))
GEMINI_FALLBACK_MODELS  = [
    model.strip()
    for model in os.getenv("GEMINI_FALLBACK_MODELS", "").split(",")
    if model.strip()
]
GEMINI_RETRY_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


# ================================================================
# SYSTEM PROMPT — Định nghĩa vai trò "Chuyên gia tư vấn"
# ================================================================

SYSTEM_PROMPT = """Bạn là **Trợ lý Tư vấn Y tế Tiểu Đường** — một chuyên gia tư vấn thân thiện và đáng tin cậy cho người bệnh tiểu đường type 2 tại Việt Nam.

## Vai trò của bạn
- Cung cấp thông tin y tế chính xác, dựa trên tài liệu y khoa chuẩn
- Trả lời bằng tiếng Việt, ngôn ngữ gần gũi, dễ hiểu
- Luôn trích dẫn nguồn tài liệu khi đưa ra lời khuyên
- Khuyến khích người dùng tham khảo bác sĩ cho quyết định y tế quan trọng

## Nguyên tắc trả lời
1. **Dựa vào tài liệu**: Chỉ đưa ra lời khuyên dựa trên [TÀI LIỆU THAM KHẢO] được cung cấp
2. **Trung thực**: Nếu không có thông tin trong tài liệu, nói thẳng "Tôi không có đủ thông tin về điều này"
3. **An toàn**: Với triệu chứng nghiêm trọng, luôn hướng dẫn đến cơ sở y tế
4. **Thực tế**: Đưa ra lời khuyên cụ thể, áp dụng được cho bệnh nhân Việt Nam

## Giới hạn
- KHÔNG chẩn đoán bệnh
- KHÔNG thay thế bác sĩ
- KHÔNG tự ý điều chỉnh thuốc
- Luôn nhắc nhở tái khám định kỳ"""


def build_rag_prompt(query: str, retrieved_chunks: List[Dict]) -> str:
    """
    Ghép context từ Vector DB vào prompt.

    Đây là "AUGMENT" trong RAG — tăng cường prompt với kiến thức thực.

    Args:
        query: Câu hỏi của user
        retrieved_chunks: Chunks liên quan từ ChromaDB

    Returns:
        Prompt đầy đủ gửi cho Gemini
    """
    if not retrieved_chunks:
        # Không có context → dùng kiến thức chung (ít chính xác hơn)
        return f"""Câu hỏi: {query}

Lưu ý: Không tìm thấy tài liệu y khoa liên quan trong cơ sở dữ liệu. 
Hãy trả lời dựa trên kiến thức y khoa chung, và nhắc người dùng tham khảo bác sĩ."""

    # Ghép các chunks thành context
    context_parts = []
    for i, chunk in enumerate(retrieved_chunks, 1):
        source   = chunk["metadata"].get("source", "Không rõ nguồn")
        category = chunk["metadata"].get("category", "")
        sim      = chunk.get("similarity", 0)
        source_type = chunk["metadata"].get("source_type", "document")
        knowledge_type = chunk["metadata"].get("knowledge_type", "")
        verified = chunk["metadata"].get("verified", "true")
        source_note = ""
        if source_type == "user":
            note_type = "quy tắc trả lời" if knowledge_type == "response_rule" else "thông tin người dùng cung cấp"
            source_note = f" | Loại: {note_type} | Xác minh: {verified}"

        context_parts.append(
            f"[Tài liệu {i}] (Nguồn: {source} | Danh mục: {category} | Độ liên quan: {sim:.0%}{source_note})\n"
            f"{chunk['text']}"
        )

    context_block = "\n\n---\n\n".join(context_parts)

    prompt = f"""## TÀI LIỆU THAM KHẢO
Dưới đây là các tài liệu y khoa liên quan đến câu hỏi:

{context_block}

---

## CÂU HỎI CỦA NGƯỜI DÙNG
{query}

---

## YÊU CẦU TRẢ LỜI
Dựa vào các tài liệu tham khảo trên, hãy:
1. Trả lời câu hỏi một cách rõ ràng, thực tế
2. Trích dẫn tài liệu nào bạn dùng (ví dụ: "Theo [Tài liệu 2]...")
3. Đưa ra lời khuyên cụ thể, có thể thực hiện được
4. Nếu dùng nguồn "Người dùng cung cấp", hãy nói rõ đó là thông tin người dùng góp ý/chưa kiểm chứng, không xem là nguồn y khoa chính thức
5. Nếu dùng nguồn loại "quy tắc trả lời", hãy dùng nó để định hướng cách hiểu câu hỏi và truy xuất kiến thức liên quan, nhưng vẫn ưu tiên tài liệu y khoa chính thức cho nội dung tư vấn
6. Kết thúc bằng một lưu ý nhắc nhở tham khảo bác sĩ nếu cần"""

    return prompt


class LLMAPIError(RuntimeError):
    """Raised when Gemini API returns an error or an unusable response."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def _gemini_payload(contents: List[Dict]) -> Dict:
    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": MAX_TOKENS,
            "temperature": LLM_TEMPERATURE,
        },
    }

    if GEMINI_THINKING_BUDGET >= 0:
        payload["generationConfig"]["thinkingConfig"] = {
            "thinkingBudget": GEMINI_THINKING_BUDGET
        }

    return payload


def _extract_gemini_text(data: Dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        feedback = data.get("promptFeedback") or {}
        reason = feedback.get("blockReason") or data.get("error", {}).get("message")
        raise LLMAPIError(f"Gemini không trả về candidate. {reason or ''}".strip())

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if part.get("text"))
    if not text:
        finish_reason = candidates[0].get("finishReason", "unknown")
        raise LLMAPIError(f"Gemini không trả về text. finishReason={finish_reason}")
    return text


def _gemini_error_message(response: requests.Response) -> str:
    try:
        data = response.json()
        return data.get("error", {}).get("message") or response.text
    except ValueError:
        return response.text


def _retry_after_seconds(response: Optional[requests.Response]) -> Optional[float]:
    if response is None:
        return None

    retry_after = response.headers.get("Retry-After")
    if not retry_after:
        return None

    try:
        value = float(retry_after)
    except ValueError:
        return None

    return value if value > 0 else None


def _retry_delay(attempt: int, response: Optional[requests.Response] = None) -> float:
    retry_after = _retry_after_seconds(response)
    if retry_after is not None:
        return min(retry_after, LLM_RETRY_MAX_DELAY)

    backoff = LLM_RETRY_BASE_DELAY * (2 ** max(attempt - 1, 0))
    jitter = random.uniform(0, min(0.5, LLM_RETRY_BASE_DELAY))
    return min(backoff + jitter, LLM_RETRY_MAX_DELAY)


def _dedupe_models(models: List[str]) -> List[str]:
    seen = set()
    result = []
    for model in models:
        if model and model not in seen:
            seen.add(model)
            result.append(model)
    return result


def _looks_like_user_knowledge(text: str) -> bool:
    if not USER_KNOWLEDGE_ENABLED:
        return False

    normalized = " " + " ".join(text.lower().split()) + " "
    if len(normalized.strip()) < USER_KNOWLEDGE_MIN_CHARS:
        return False

    question_markers = (
        "?",
        " là gì",
        " la gi",
        " bao nhiêu",
        " bao nhieu",
        " tại sao",
        " tai sao",
        " vì sao",
        " vi sao",
        " như thế nào",
        " nhu the nao",
        " có nên",
        " co nen",
        " được không",
        " duoc khong",
        " phải không",
        " phai khong",
    )
    if any(marker in normalized for marker in question_markers):
        return False

    explicit_markers = (
        " bổ sung ",
        " bo sung ",
        " góp ý ",
        " gop y ",
    )
    if any(marker in normalized for marker in explicit_markers):
        return True

    knowledge_markers = (
        " là khi ",
        " la khi ",
        " bao gồm ",
        " bao gom ",
        " gồm ",
        " gom ",
        " có nghĩa là ",
        " co nghia la ",
        " được hiểu là ",
        " duoc hieu la ",
        " triệu chứng ",
        " trieu chung ",
        " dấu hiệu ",
        " dau hieu ",
        " nguyên nhân ",
        " nguyen nhan ",
        " cách xử trí ",
        " cach xu tri ",
    )
    medical_markers = (
        " tiểu đường ",
        " tieu duong ",
        " đái tháo đường ",
        " dai thao duong ",
        " đường huyết ",
        " duong huyet ",
        " hạ đường huyết ",
        " ha duong huyet ",
        " tăng đường huyết ",
        " tang duong huyet ",
        " insulin ",
        " metformin ",
        " hba1c ",
        " glucose ",
        " bác sĩ ",
        " bac si ",
        " thuốc ",
        " thuoc ",
        " triệu chứng ",
        " trieu chung ",
        " dấu hiệu ",
        " dau hieu ",
    )
    definition_markers = (" là ", " la ")

    return (
        any(marker in normalized for marker in knowledge_markers)
        or (
            any(marker in normalized for marker in definition_markers)
            and any(marker in normalized for marker in medical_markers)
        )
    )


def _looks_like_user_response_rule(text: str) -> bool:
    if not USER_KNOWLEDGE_ENABLED:
        return False

    normalized = " " + " ".join(text.lower().split()) + " "
    if len(normalized.strip()) < USER_KNOWLEDGE_MIN_CHARS:
        return False

    trigger_markers = (
        " nếu hỏi ",
        " neu hoi ",
        " nếu người dùng hỏi ",
        " neu nguoi dung hoi ",
        " nếu tôi hỏi ",
        " neu toi hoi ",
        " khi hỏi ",
        " khi hoi ",
        " khi người dùng hỏi ",
        " khi nguoi dung hoi ",
        " khi tôi nói ",
        " khi toi noi ",
        " nếu tôi nói ",
        " neu toi noi ",
    )
    action_markers = (
        " thì bạn ",
        " thi ban ",
        " hãy trả lời ",
        " hay tra loi ",
        " cần trả lời ",
        " can tra loi ",
        " cần đưa ra ",
        " can dua ra ",
        " trả lời như ",
        " tra loi nhu ",
        " trích xuất ",
        " trich xuat ",
        " liên quan đến ",
        " lien quan den ",
    )
    return (
        any(marker in normalized for marker in trigger_markers)
        and any(marker in normalized for marker in action_markers)
    )


def _user_knowledge_query(query: str) -> str:
    return (
        f"{query}\n\n"
        "[Ngữ cảnh xử lý: Người dùng đang góp ý hoặc cung cấp thông tin mới. "
        "Hãy xác nhận đã ghi nhận, tóm tắt ngắn thông tin người dùng cung cấp, "
        "và nếu đây là nội dung y tế thì nói rõ thông tin này cần được đối chiếu "
        "với tài liệu y khoa hoặc bác sĩ. Không nói là không có thông tin nếu "
        "context có nguồn 'Người dùng cung cấp'.]"
    )


def _user_learning_query(query: str, learning_type: Optional[str]) -> str:
    if learning_type == "response_rule":
        return (
            f"{query}\n\n"
            "[Ngữ cảnh xử lý: Người dùng đang dạy một quy tắc trả lời mới. "
            "Hãy xác nhận đã ghi nhớ quy tắc, tóm tắt ngắn điều kiện kích hoạt "
            "và hướng trả lời sẽ dùng trong tương lai. Không tư vấn y tế dài ở lượt này, "
            "chỉ nói rõ quy tắc này là hướng dẫn do người dùng cung cấp và vẫn cần ưu tiên "
            "tài liệu y khoa chính thức khi trả lời.]"
        )

    if learning_type == "knowledge":
        return _user_knowledge_query(query)

    return query


class RAGPipeline:
    """
    Pipeline RAG hoàn chỉnh: Retrieve → Augment → Generate.

    Sử dụng:
        pipeline = RAGPipeline()
        answer = pipeline.answer("Tôi bị tiểu đường, ăn phở được không?")
        print(answer["response"])
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key or api_key.lower().startswith(("xxx", "your_", "your-")):
            raise ValueError(
                "Chua cau hinh GEMINI_API_KEY!\n"
                "Hay dien GEMINI_API_KEY vao file .env."
            )

        self.api_key = api_key
        self.model_candidates = _dedupe_models([LLM_MODEL, *GEMINI_FALLBACK_MODELS])
        self.generate_url = f"{GEMINI_API_BASE}/models/{LLM_MODEL}:generateContent"
        self.stream_url = f"{GEMINI_API_BASE}/models/{LLM_MODEL}:streamGenerateContent"
        self.headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        self.indexer = VectorIndexer()
        stats = self.indexer.get_stats()
        if stats["total_chunks"] == 0:
            raise RuntimeError(
                "Vector Database trong!\n"
                "Hay chay: python src/rag/indexer.py"
            )
        logger.success(f"RAG Pipeline san sang ({stats['total_chunks']} chunks, model={LLM_MODEL})")

    def _generate_url_for_model(self, model: str) -> str:
        return f"{GEMINI_API_BASE}/models/{model}:generateContent"

    def _post_gemini(self, contents: List[Dict]) -> requests.Response:
        payload = _gemini_payload(contents)
        last_error: Optional[LLMAPIError] = None
        total_attempts = LLM_MAX_RETRIES + 1

        for model_index, model in enumerate(self.model_candidates, 1):
            url = self._generate_url_for_model(model)

            if model != LLM_MODEL:
                logger.warning(f"Thu fallback Gemini model: {model}")

            for attempt in range(1, total_attempts + 1):
                response: Optional[requests.Response] = None
                try:
                    response = requests.post(
                        url,
                        headers=self.headers,
                        json=payload,
                        timeout=LLM_TIMEOUT,
                    )
                except requests.RequestException as exc:
                    last_error = LLMAPIError(
                        f"Gemini request failed: {exc}",
                        retryable=True,
                    )
                else:
                    if response.ok:
                        return response

                    retryable = response.status_code in GEMINI_RETRY_STATUS_CODES
                    last_error = LLMAPIError(
                        f"Gemini API error {response.status_code}: {_gemini_error_message(response)}",
                        status_code=response.status_code,
                        retryable=retryable,
                    )

                    if not retryable:
                        raise last_error

                has_more_attempts = attempt < total_attempts
                has_more_models = model_index < len(self.model_candidates)
                if has_more_attempts:
                    delay = _retry_delay(attempt, response)
                    logger.warning(
                        f"Gemini tam thoi loi, thu lai {attempt}/{LLM_MAX_RETRIES} "
                        f"sau {delay:.1f}s: {last_error}"
                    )
                    time.sleep(delay)
                elif has_more_models:
                    logger.warning(f"Gemini model {model} van loi: {last_error}")

        if last_error:
            raise last_error

        raise LLMAPIError("Gemini API error: khong co model nao duoc cau hinh")

    def _learn_from_user_if_applicable(self, text: str) -> Dict:
        learning_type: Optional[str] = None
        if _looks_like_user_response_rule(text):
            learning_type = "response_rule"
        elif _looks_like_user_knowledge(text):
            learning_type = "knowledge"

        if not learning_type:
            return {"saved": False, "type": None}

        try:
            stored = self.indexer.add_user_knowledge(
                text,
                category=(
                    USER_RESPONSE_RULE_CATEGORY
                    if learning_type == "response_rule"
                    else "user_knowledge"
                ),
                knowledge_type=learning_type,
            )
            if stored.get("duplicate"):
                logger.debug("Thông tin người dùng đã có trong vector DB")
            return {"saved": True, "type": learning_type}
        except Exception as exc:
            logger.warning(f"Không lưu được thông tin người dùng: {exc}")
            return {"saved": False, "type": None}

    def _retrieve_matching_user_rules(self, query: str) -> List[Dict]:
        if not USER_KNOWLEDGE_ENABLED:
            return []

        try:
            rules = self.indexer.search(
                query,
                top_k=USER_RULE_TOP_K,
                category_filter=USER_RESPONSE_RULE_CATEGORY,
            )
        except Exception as exc:
            logger.warning(f"Không truy hồi được quy tắc người dùng: {exc}")
            return []

        matched = [
            rule for rule in rules
            if rule.get("similarity", 0) >= USER_RULE_MIN_SIMILARITY
        ]
        if matched:
            logger.debug(f"  Dùng {len(matched)} quy tắc người dùng để mở rộng truy vấn")
        return matched

    def _expanded_query_with_rules(self, query: str, rules: List[Dict]) -> str:
        if not rules:
            return query

        rule_text = "\n".join(
            f"- {rule['text'][:USER_RULE_EXPANSION_MAX_CHARS]}"
            for rule in rules
        )
        return (
            f"{query}\n\n"
            "Quy tắc trả lời người dùng đã dạy có liên quan:\n"
            f"{rule_text}\n\n"
            "Hãy dùng các khái niệm y tế trong quy tắc trên để tìm tài liệu liên quan."
        )

    def _merge_chunks(self, chunks: List[Dict]) -> List[Dict]:
        seen = set()
        merged = []
        for chunk in chunks:
            chunk_id = chunk.get("id") or f"{chunk['metadata'].get('source', '')}:{chunk['text']}"
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            merged.append(chunk)
        return merged

    def retrieve(self, query: str, top_k: int = TOP_K) -> List[Dict]:
        """
        BƯỚC R: RETRIEVE — Tìm tài liệu liên quan.

        Dùng semantic search (không phải keyword search):
        → Tìm theo nghĩa, không phải từ khóa chính xác
        → "ăn cơm được không" vẫn tìm được "chế độ ăn tinh bột"
        """
        logger.debug(f"🔍 Retrieve: '{query[:50]}...' (top_{top_k})")
        matched_rules = self._retrieve_matching_user_rules(query)
        search_query = self._expanded_query_with_rules(query, matched_rules)
        chunks = self.indexer.search(search_query, top_k=top_k)

        # Lọc chunk có độ tương đồng quá thấp (không liên quan)
        MIN_SIMILARITY = 0.3
        filtered = [c for c in chunks if c["similarity"] >= MIN_SIMILARITY]
        relevant = self._merge_chunks([*matched_rules, *filtered])

        if len(filtered) < len(chunks):
            logger.debug(f"  Lọc {len(chunks)-len(filtered)} chunks không liên quan")

        logger.debug(f"  ✓ Tìm được {len(relevant)} chunks liên quan")
        return relevant

    def generate(
        self,
        query: str,
        context_chunks: List[Dict],
        learning_type: Optional[str] = None,
    ) -> str:
        """
        BƯỚC G: GENERATE — Sinh câu trả lời từ Gemini.

        Gửi prompt = system_prompt + context + query → Gemini
        Gemini đọc context và sinh câu trả lời chính xác.
        """
        prompt_query = _user_learning_query(query, learning_type)
        prompt = build_rag_prompt(prompt_query, context_chunks)

        logger.debug(f"💬 Gọi Gemini ({LLM_MODEL})...")
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        response = self._post_gemini(contents)
        return _extract_gemini_text(response.json())

    def answer(self, query: str, top_k: int = TOP_K) -> Dict:
        """
        Pipeline đầy đủ: nhận câu hỏi → trả về câu trả lời có nguồn.

        Args:
            query: Câu hỏi của user
            top_k: Số tài liệu tham khảo

        Returns:
            Dict với keys:
            - query: câu hỏi gốc
            - response: câu trả lời của AI
            - sources: danh sách nguồn tài liệu đã dùng
            - chunks_used: số chunks tham khảo
        """
        logger.info(f"\n{'='*50}")
        logger.info(f"❓ Query: {query}")

        learning = self._learn_from_user_if_applicable(query)

        # R: Retrieve
        chunks = self.retrieve(query, top_k=top_k)

        # A: Augment (xảy ra trong build_rag_prompt)
        # G: Generate
        response = self.generate(query, chunks, learning_type=learning["type"])

        # Tổng hợp nguồn tham khảo
        sources = []
        seen = set()
        for chunk in chunks:
            src = chunk["metadata"].get("source", "unknown")
            if src not in seen:
                seen.add(src)
                sources.append({
                    "source": src,
                    "category": chunk["metadata"].get("category", ""),
                    "similarity": chunk["similarity"],
                })

        result = {
            "query": query,
            "response": response,
            "sources": sources,
            "chunks_used": len(chunks),
            "learned_from_user": learning["saved"],
            "learning_type": learning["type"],
        }

        logger.success(f"✅ Đã trả lời dựa trên {len(chunks)} chunks từ {len(sources)} nguồn")
        return result

    def answer_with_history(self, messages: List[Dict], top_k: int = TOP_K) -> Dict:
        """
        Trả lời trong hội thoại nhiều lượt (multi-turn).

        Lấy câu hỏi mới nhất để retrieve, nhưng gửi toàn bộ
        lịch sử hội thoại cho Gemini để giữ ngữ cảnh.

        Args:
            messages: List[{"role": "user"|"assistant", "content": str}]
            top_k: Số chunks tham khảo

        Returns:
            Dict tương tự answer()
        """
        # Lấy câu hỏi mới nhất để retrieve
        last_user_msg = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        if not last_user_msg:
            return {"query": "", "response": "Không có câu hỏi.", "sources": [], "chunks_used": 0}

        learning = self._learn_from_user_if_applicable(last_user_msg)

        # Retrieve dựa trên câu hỏi mới nhất
        chunks = self.retrieve(last_user_msg, top_k=top_k)

        history_lines = []
        for msg in messages:
            speaker = "Người dùng" if msg["role"] == "user" else "Trợ lý"
            history_lines.append(f"{speaker}: {msg['content']}")

        prompt = (
            "## LỊCH SỬ HỘI THOẠI\n"
            + "\n".join(history_lines)
            + "\n\n---\n\n"
            + build_rag_prompt(
                _user_learning_query(last_user_msg, learning["type"]),
                chunks,
            )
        )
        logger.debug(f"💬 Gọi Gemini ({LLM_MODEL}) với lịch sử hội thoại...")
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        llm_response = self._post_gemini(contents)
        response = _extract_gemini_text(llm_response.json())
        sources = list({c["metadata"]["source"] for c in chunks})

        return {
            "query": last_user_msg,
            "response": response,
            "sources": [{"source": s} for s in sources],
            "chunks_used": len(chunks),
            "learned_from_user": learning["saved"],
            "learning_type": learning["type"],
        }


# ── DEMO CHẠY TRỰC TIẾP ─────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🤖 RAG PIPELINE — Demo Chatbot Y Tế")
    logger.info("=" * 60)

    try:
        pipeline = RAGPipeline()
    except (ValueError, RuntimeError) as e:
        logger.error(str(e))
        sys.exit(1)

    # Danh sách câu hỏi demo
    test_questions = [
        "Tôi bị tiểu đường type 2, sáng nay lỡ ăn 1 bát phở thì nên làm gì?",
        "Chỉ số HbA1c bao nhiêu là bình thường?",
        "Người tiểu đường có thể tập thể dục không?",
        "Thuốc Metformin uống lúc nào là tốt nhất?",
    ]

    for question in test_questions:
        result = pipeline.answer(question, top_k=3)
        print(f"\n{'='*60}")
        print(f"❓ {result['query']}")
        print(f"{'='*60}")
        print(result["response"])
        print(f"\n📚 Nguồn: {', '.join(s['source'] for s in result['sources'])}")
        print(f"📦 Dùng {result['chunks_used']} chunks")
        input("\n[Enter để tiếp tục...]\n")
