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
import re
import random
import time
import unicodedata
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

import requests
sys.path.append(str(Path(__file__).parent.parent.parent))
from src.rag.indexer import USER_RESPONSE_RULE_CATEGORY, VectorIndexer

# ── Cấu hình ────────────────────────────────────────────────
_configured_model       = os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")
LLM_MODEL               = "gemini-2.5-flash" if _configured_model.startswith("claude") else _configured_model
MAX_TOKENS              = int(os.getenv("MAX_TOKENS", 2048))
TOP_K                   = int(os.getenv("TOP_K_RESULTS", 5))
LLM_TEMPERATURE         = float(os.getenv("LLM_TEMPERATURE", 0.2))
LLM_TIMEOUT             = int(os.getenv("LLM_TIMEOUT", 120))
LLM_MAX_RETRIES         = int(os.getenv("LLM_MAX_RETRIES", 3))
LLM_RETRY_BASE_DELAY    = float(os.getenv("LLM_RETRY_BASE_DELAY", 1.0))
LLM_RETRY_MAX_DELAY     = float(os.getenv("LLM_RETRY_MAX_DELAY", 10.0))
USER_KNOWLEDGE_ENABLED  = os.getenv("USER_KNOWLEDGE_ENABLED", "false").lower() not in {"0", "false", "no"}
USER_KNOWLEDGE_MIN_CHARS = int(os.getenv("USER_KNOWLEDGE_MIN_CHARS", 40))
USER_RULE_TOP_K         = int(os.getenv("USER_RULE_TOP_K", 3))
USER_RULE_MIN_SIMILARITY = float(os.getenv("USER_RULE_MIN_SIMILARITY", 0.18))
USER_RULE_EXPANSION_MAX_CHARS = int(os.getenv("USER_RULE_EXPANSION_MAX_CHARS", 900))
GEMINI_API_BASE         = os.getenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta")
GEMINI_THINKING_BUDGET  = int(os.getenv("GEMINI_THINKING_BUDGET", 0))
_fallback_models_env = os.getenv(
    "GEMINI_FALLBACK_MODELS",
    "gemini-2.5-flash,gemini-2.0-flash-lite",
)
GEMINI_FALLBACK_MODELS  = [
    model.strip()
    for model in _fallback_models_env.split(",")
    if model.strip()
]
GEMINI_RETRY_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}

INTENT_CATEGORY_FILTERS = {
    "emergency": ["emergency", "blood_glucose", "chi_so_duong_huyet"],
    "medication": ["medication", "dieu_tri", "blood_glucose", "chi_so_duong_huyet"],
    "diet": ["diet", "che_do_an", "lifestyle", "the_duc_loi_song"],
    "blood_glucose": ["blood_glucose", "chi_so_duong_huyet", "emergency"],
    "complication": ["complication", "diagnosis", "general", "tieu_duong_type2"],
    "diagnosis": ["diagnosis", "general", "tieu_duong_type2"],
    "general": ["general", "diagnosis", "tieu_duong_type2", "lifestyle", "the_duc_loi_song"],
}


def _normalize_for_intent(text: str) -> str:
    lowered = text.lower()
    no_accents = "".join(
        ch for ch in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(ch) != "Mn"
    )
    return f" {lowered} {no_accents} "


def detect_intent(query: str) -> str:
    q = _normalize_for_intent(query)
    intent_keywords = {
        "emergency": [
            "ha duong huyet", "duong huyet thap", "ngat", "hon me", "co giat",
            "run tay", "va mo hoi", "tim dap nhanh", "kho tho", "dau nguc",
            "cap cuu", "52 mg/dl", "50 mg/dl", "duoi 70",
        ],
        "medication": [
            "thuoc", "metformin", "insulin", "gliclazide", "glimepiride",
            "sulfonylurea", "lieu", "uống thuốc", "uong thuoc", "tac dung phu",
        ],
        "diet": [
            "an", "uong", "dinh duong", "che do an", "thuc pham", "pho", "com",
            "bun", "banh mi", "trai cay", "rau", "carb", "tinh bot",
        ],
        "blood_glucose": [
            "duong huyet", "hba1c", "glucose", "mg/dl", "mmol", "do duong",
            "chi so", "sau an", "luc doi",
        ],
        "complication": [
            "bien chung", "than", "mat", "vong mac", "ban chan", "loet",
            "te bi", "than kinh", "tim mach",
        ],
        "diagnosis": [
            "chan doan", "tieu duong la gi", "dai thao duong la gi", "type 2",
            "tuyp 2", "nguyen nhan", "trieu chung",
        ],
    }
    for intent, keywords in intent_keywords.items():
        if any(keyword in q for keyword in keywords):
            return intent
    return "general"


def _extract_glucose_value(query: str) -> Optional[float]:
    normalized = _normalize_for_intent(query)
    patterns = [
        r"(\d+(?:\.\d+)?)\s*mg/dl",
        r"(\d+(?:\.\d+)?)\s*mmol/l",
    ]
    import re

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            try:
                value = float(match.group(1))
                if "mmol/l" in pattern:
                    return round(value * 18.0, 1)
                return value
            except ValueError:
                continue
    return None


def _is_emergency_query(query: str, patient_context: Optional[Dict] = None) -> bool:
    intent = detect_intent(query)
    if intent == "emergency":
        return True

    q = _normalize_for_intent(query)
    emergency_markers = [
        "kho tho", "dau nguc", "ngat", "hon me", "co giat", "luc lac",
        "tim dap nhanh", "va mo hoi", "run tay", "lanh toat mo hoi",
    ]
    if any(marker in q for marker in emergency_markers):
        return True

    glucose = _extract_glucose_value(query)
    if glucose is not None and glucose < 70:
        return True

    if patient_context:
        recent_labs = patient_context.get("recent_labs", {})
        fasting = recent_labs.get("fasting_glucose", {})
        hba1c = recent_labs.get("hba1c", {})
        for value in (fasting.get("value"), hba1c.get("value")):
            try:
                if value is not None and float(value) < 70:
                    return True
            except (TypeError, ValueError):
                pass
    return False


def _build_emergency_response(query: str) -> Dict:
    response = (
        "Đây có thể là tình huống khẩn cấp liên quan đến đường huyết. "
        "Nếu bạn tỉnh táo và đang bị hạ đường huyết, hãy dùng quy tắc 15-15: "
        "uống 15g đường nhanh, đợi 15 phút, đo lại. "
        "Nếu có rối loạn ý thức, khó thở, đau ngực, ngất, co giật, hoặc không tự uống được, "
        "gọi cấp cứu hoặc đến cơ sở y tế ngay lập tức."
    )
    return {
        "query": query,
        "response": response,
        "sources": [],
        "chunks_used": 0,
        "learned_from_user": False,
        "learning_type": None,
        "triage_mode": "emergency",
    }


def _format_minutes_clock(total_minutes: int) -> str:
    total_minutes %= 24 * 60
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _extract_meal_time_minutes(query: str) -> Optional[int]:
    normalized = _normalize_for_intent(query)
    time_patterns = [
        r"(?<!\d)(\d{1,2})(?:\s*[:h]\s*(\d{1,2}))?\s*(?:gio|g|h)?\b",
    ]

    for pattern in time_patterns:
        for match in re.finditer(pattern, normalized):
            window_start = max(0, match.start() - 24)
            window_end = min(len(normalized), match.end() + 16)
            window = normalized[window_start:window_end]
            if "phut" in window or "mg/dl" in window or "mmol/l" in window:
                continue
            if not any(marker in window for marker in ("luc", "vao", "an", "bua", "toi", "sang", "trua")):
                continue

            try:
                hour = int(match.group(1))
                minute = int(match.group(2) or 0)
            except ValueError:
                continue

            if hour > 23 or minute > 59:
                continue

            if any(marker in normalized for marker in ("toi", "chieu", "dem")) and hour < 12:
                hour += 12
            elif any(marker in normalized for marker in ("sang",)) and hour == 12:
                hour = 0

            return hour * 60 + minute

    return None


def _is_premeal_timing_query(query: str) -> bool:
    normalized = _normalize_for_intent(query)
    medication_markers = ("tiem", "insulin", "thuoc", "uong thuoc", "uống thuốc")
    meal_markers = (
        "truoc an",
        "truoc bua",
        "truoc khi an",
        "an toi",
        "an sang",
        "an trua",
        "an luc",
        "luc an",
        "luc may gio",
        "may gio",
        "mấy giờ",
    )

    if any(marker in normalized for marker in ("tiem truoc an", "insulin truoc an", "thuoc truoc an")):
        return True

    if any(marker in normalized for marker in medication_markers) and any(marker in normalized for marker in meal_markers):
        return True

    return False


def _build_premeal_timing_response(query: str) -> Dict:
    meal_minutes = _extract_meal_time_minutes(query)
    if meal_minutes is None:
        response = (
            "Nếu đây là thuốc hoặc insulin tiêm trước bữa ăn theo đơn, bạn nên tiêm trước ăn 30 phút. "
            "Nếu trên đơn bác sĩ có hướng dẫn khác, hãy theo đúng đơn đó và hỏi lại bác sĩ hoặc dược sĩ."
        )
    else:
        meal_time = _format_minutes_clock(meal_minutes)
        injection_time = _format_minutes_clock(meal_minutes - 30)
        response = (
            f"Nếu bạn ăn lúc {meal_time}, thì thời điểm tiêm là {injection_time} "
            "(trước ăn 30 phút). "
            "Lưu ý: đây là quy tắc chung cho thuốc hoặc insulin tiêm trước bữa ăn; "
            "nếu loại thuốc trên đơn có hướng dẫn khác, hãy theo đúng đơn bác sĩ."
        )

    return {
        "query": query,
        "response": response,
        "sources": [],
        "chunks_used": 0,
        "learned_from_user": False,
        "learning_type": None,
        "triage_mode": "premeal_timing",
    }


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


def _format_patient_context(patient_context: Optional[Dict]) -> str:
    if not patient_context:
        return ""

    demographics = patient_context.get("demographics", {})
    diagnosis = patient_context.get("diagnosis", {})
    medications = patient_context.get("current_medications", [])
    recent_labs = patient_context.get("recent_labs", {})

    meds = ", ".join(
        med.get("name", "").strip()
        for med in medications
        if isinstance(med, dict) and med.get("name")
    ) or "khong co"

    hba1c = recent_labs.get("hba1c", {})
    fasting = recent_labs.get("fasting_glucose", {})

    lines = [
        "[HO SO BENH NHAN]",
        f"- Tuoi: {demographics.get('age', 'khong ro')}",
        f"- Gioi tinh: {demographics.get('gender', 'khong ro')}",
        f"- Loai dai thao duong: {diagnosis.get('diabetes_type', 'khong ro')}",
        f"- Bien chung: {', '.join(diagnosis.get('complications', [])) or 'khong co'}",
        f"- Benh kem theo: {', '.join(diagnosis.get('comorbidities', [])) or 'khong co'}",
        f"- Thuoc dang dung: {meds}",
        f"- HbA1c gan nhat: {hba1c.get('value', 'khong ro')} {hba1c.get('unit', '')}".strip(),
        f"- Duong huyet luc doi: {fasting.get('value', 'khong ro')} {fasting.get('unit', '')}".strip(),
        f"- Di ung: {', '.join(patient_context.get('allergies', [])) or 'khong co'}",
        f"- Han che an uong: {', '.join(patient_context.get('dietary_restrictions', [])) or 'khong co'}",
    ]
    return "\n".join(lines)


def build_rag_prompt_with_patient_context(
    query: str,
    retrieved_chunks: List[Dict],
    patient_context: Optional[Dict] = None,
) -> str:
    base_prompt = build_rag_prompt(query, retrieved_chunks)
    patient_block = _format_patient_context(patient_context)
    if not patient_block:
        return base_prompt

    return (
        "[NGUOI DUNG - HO SO BENH NHAN]\n"
        f"{patient_block}\n\n"
        "[TAI LIEU THAM KHAO]\n"
        f"{base_prompt}"
    )


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

    def _build_metadata_filter(self, intent: str) -> Optional[Dict]:
        categories = INTENT_CATEGORY_FILTERS.get(intent, INTENT_CATEGORY_FILTERS["general"])
        conditions = [{"category": {"$in": categories}}]

        if intent in {"emergency", "medication"}:
            conditions.append({"verified_by_doctor": {"$eq": True}})

        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def _metadata_score(self, chunk: Dict, intent: str) -> float:
        meta = chunk.get("metadata", {})
        semantic = max(0.0, min(float(chunk.get("similarity", 0.0)), 1.0))
        priority = meta.get("source_priority", 4)
        try:
            priority = int(priority)
        except (TypeError, ValueError):
            priority = 4

        source_score = max(0.0, min((6 - priority) / 5, 1.0))
        verified = meta.get("verified_by_doctor", False)
        verified_score = 1.0 if verified is True or str(verified).lower() == "true" else 0.0
        language = str(meta.get("language", "")).lower()
        language_score = 1.0 if language == "vi" else 0.75 if language == "en" else 0.5
        category_score = 1.0 if meta.get("category") in INTENT_CATEGORY_FILTERS.get(intent, []) else 0.0

        return round(
            0.72 * semantic
            + 0.12 * source_score
            + 0.08 * verified_score
            + 0.05 * language_score
            + 0.03 * category_score,
            4,
        )

    def _rerank_chunks(self, chunks: List[Dict], intent: str, top_k: int) -> List[Dict]:
        reranked = []
        for chunk in chunks:
            enriched = dict(chunk)
            enriched["final_score"] = self._metadata_score(chunk, intent)
            enriched["intent"] = intent
            reranked.append(enriched)
        reranked.sort(key=lambda item: item.get("final_score", 0), reverse=True)
        return reranked[:top_k]

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

    def _retrieve_metadata_aware(self, query: str, top_k: int) -> List[Dict]:
        intent = detect_intent(query)
        logger.debug(f"Retrieve intent={intent}: '{query[:50]}...' (top_{top_k})")

        matched_rules = self._retrieve_matching_user_rules(query)
        search_query = self._expanded_query_with_rules(query, matched_rules)
        where_filter = self._build_metadata_filter(intent)
        candidate_k = max(top_k * 4, 12)

        try:
            chunks = self.indexer.search(
                search_query,
                top_k=candidate_k,
                where_filter=where_filter,
            )
        except Exception as exc:
            logger.warning(f"Metadata filter search failed, fallback to semantic only: {exc}")
            chunks = self.indexer.search(search_query, top_k=candidate_k)

        min_similarity = 0.24 if intent in {"general", "diagnosis"} else 0.28
        filtered = [c for c in chunks if c["similarity"] >= min_similarity]
        if not filtered:
            filtered = chunks

        ranked = self._rerank_chunks(filtered, intent=intent, top_k=top_k)
        relevant = self._merge_chunks([*matched_rules, *ranked])
        logger.debug(f"  -> Retrieved {len(relevant)} chunks after rerank")
        return relevant

    def generate(
        self,
        query: str,
        context_chunks: List[Dict],
        learning_type: Optional[str] = None,
        patient_context: Optional[Dict] = None,
    ) -> str:
        """
        BƯỚC G: GENERATE — Sinh câu trả lời từ Gemini.

        Gửi prompt = system_prompt + context + query → Gemini
        Gemini đọc context và sinh câu trả lời chính xác.
        """
        prompt_query = _user_learning_query(query, learning_type)
        prompt = build_rag_prompt_with_patient_context(
            prompt_query,
            context_chunks,
            patient_context=patient_context,
        )

        logger.debug(f"💬 Gọi Gemini ({LLM_MODEL})...")
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        response = self._post_gemini(contents)
        return _extract_gemini_text(response.json())

    def answer(
        self,
        query: str,
        top_k: int = TOP_K,
        patient_context: Optional[Dict] = None,
    ) -> Dict:
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
        logger.info(f"❓ Query len={len(query)} intent={detect_intent(query)}")

        if _is_emergency_query(query, patient_context=patient_context):
            logger.warning("Emergency triage triggered before LLM generation")
            return _build_emergency_response(query)

        if _is_premeal_timing_query(query):
            logger.info("Pre-meal timing shortcut triggered before LLM generation")
            return _build_premeal_timing_response(query)

        learning = self._learn_from_user_if_applicable(query)

        # R: Retrieve
        chunks = self._retrieve_metadata_aware(query, top_k=top_k)

        # A: Augment (xảy ra trong build_rag_prompt)
        # G: Generate
        response = self.generate(
            query,
            chunks,
            learning_type=learning["type"],
            patient_context=patient_context,
        )

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

    def answer_with_history(
        self,
        messages: List[Dict],
        top_k: int = TOP_K,
        patient_context: Optional[Dict] = None,
    ) -> Dict:
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

        if _is_emergency_query(last_user_msg, patient_context=patient_context):
            logger.warning("Emergency triage triggered in history flow")
            emergency = _build_emergency_response(last_user_msg)
            emergency["query"] = last_user_msg
            return emergency

        if _is_premeal_timing_query(last_user_msg):
            logger.info("Pre-meal timing shortcut triggered in history flow")
            timing = _build_premeal_timing_response(last_user_msg)
            timing["query"] = last_user_msg
            return timing

        learning = self._learn_from_user_if_applicable(last_user_msg)

        # Retrieve dựa trên câu hỏi mới nhất
        chunks = self._retrieve_metadata_aware(last_user_msg, top_k=top_k)

        history_lines = []
        for msg in messages:
            speaker = "Người dùng" if msg["role"] == "user" else "Trợ lý"
            history_lines.append(f"{speaker}: {msg['content']}")

        prompt = (
            "## LỊCH SỬ HỘI THOẠI\n"
            + "\n".join(history_lines)
            + "\n\n---\n\n"
            + build_rag_prompt_with_patient_context(
                _user_learning_query(last_user_msg, learning["type"]),
                chunks,
                patient_context=patient_context,
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
