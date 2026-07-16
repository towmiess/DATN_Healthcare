"""
src/utils/text_normalize.py
──────────────────────────────
Chuẩn hóa các biến thể chính tả tiếng Việt thường gặp trong tài liệu y khoa
crawl/OCR, để hiển thị nhất quán cho người dùng (cả lúc ingest và lúc LLM
sinh câu trả lời).

Ví dụ: "thai kì" / "thai kỳ" → "thai kỳ"
       "týp 1" / "típ 1" / "type 1" → "tuýp 1"
"""

import re

# Mỗi tuple: (regex pattern không phân biệt hoa/thường, chuỗi thay thế)
# Thứ tự quan trọng: pattern dài/cụ thể hơn đặt trước để tránh thay thế sai.
_REPLACEMENTS = [
    # "kì" → "kỳ" (thai kì, kì lạ về chỉ số, định kì...) — chỉ áp dụng khi
    # đứng riêng như 1 âm tiết, tránh phá các từ ghép khác chứa "ki"
    (r"\bthai\s*k[iì]\b",        "thai kỳ"),
    (r"\bđịnh\s*k[iì]\b",        "định kỳ"),
    (r"\bgiai\s*đoạn\s*k[iì]\b", "giai đoạn kỳ"),
    (r"\bk[iì]\s*kinh\b",        "kỳ kinh"),
    (r"\bk[iì]\s*thai\b",        "kỳ thai"),

    # "týp"/"típ"/"type" (số) → "tuýp" (số)  — áp dụng cho cả số La Mã/Ả Rập
    # [yýỳỷỹi í] phủ các biến thể dấu của y/i thường gặp do lỗi font/OCR
    (r"\bt[yýỳỷỹií]p\s*(\d+)\b",      r"tuýp \1"),
    (r"\btype\s*(\d+)\b",             r"tuýp \1"),
    (r"\bt[yýỳỷỹií]p\s+I\b",          "tuýp 1"),
    (r"\bt[yýỳỷỹií]p\s+II\b",         "tuýp 2"),
    (r"\btype\s+I\b",                 "tuýp 1"),
    (r"\btype\s+II\b",                "tuýp 2"),

    # Một vài lỗi OCR/font phổ biến khác có thể bổ sung dần
    (r"\btiểu\s*đường\s*type\b", "tiểu đường tuýp"),
]

_COMPILED = [(re.compile(pat, re.IGNORECASE), repl) for pat, repl in _REPLACEMENTS]

# ── Patterns dọn dẹp câu trả lời LLM (lớp bảo vệ thứ 2, không phụ thuộc ───
#    hoàn toàn vào việc LLM tuân thủ prompt) ──────────────────────────────
_CLEANUP_PATTERNS = [
    # Xóa footer "Nguồn tham khảo" và số trích dẫn còn sót trong câu trả lời
    (re.compile(r"(?is)\n?\s*Nguồn tham khảo\s*:.*$", re.IGNORECASE), ""),
    (re.compile(r"(?<!\w)\[\s*\d{1,3}\s*\](?:\s*\[\s*\d{1,3}\s*\])*"), ""),

    # "Theo [Tài liệu 4]," / "Dựa trên [Tài liệu 4]..." ở bất kỳ vị trí nào
    # → bỏ cụm dẫn nhập, chỉ giữ lại "[4]" (kèm dấu phẩy/khoảng trắng theo sau nếu có)
    (re.compile(r"(?:Theo|Dựa trên|Căn cứ vào)\s*\[Tài liệu\s*(\d+)\]\s*,?\s*",
                re.IGNORECASE),
     r"[\1] "),
    # "[Tài liệu 4]" còn sót lại (không có cụm dẫn nhập phía trước) → "[4]"
    (re.compile(r"\[Tài liệu\s*(\d+)\]", re.IGNORECASE), r"[\1]"),
    # "(xem tài liệu 4)" hoặc biến thể không ngoặc vuông
    (re.compile(r"\(?\s*(?:xem\s+)?tài liệu\s*(\d+)\s*\)?", re.IGNORECASE), r"[\1]"),

    # Bỏ tên tiếng Anh lặp lại ngay sau heading dạng:
    #   "Tiểu đường tuýp 1 (tuýp 1 Diabetes):"  → "Tiểu đường tuýp 1:"
    #   "Tiểu đường thai kỳ (Gestational Diabetes):" → "Tiểu đường thai kỳ:"
    (re.compile(r"\s*\([^()]*Diabetes[^()]*\)\s*:", re.IGNORECASE), ":"),
    (re.compile(r"\s*\([^()]*Diabetes[^()]*\)", re.IGNORECASE), ""),
]


def clean_llm_response(text: str) -> str:
    """
    Dọn câu trả lời LLM sau khi sinh ra:
      1. Chuẩn hóa chính tả (kì→kỳ, type/týp→tuýp)
      2. Loại bỏ mọi dạng "[Tài liệu N]" còn sót, chuẩn hóa về "[N]"
      3. Bỏ tên tiếng Anh dư thừa trong ngoặc đơn ngay sau heading
         (ví dụ "(tuýp 1 Diabetes)", "(Gestational Diabetes)")
    An toàn gọi trên text rỗng/None, idempotent.
    """
    if not text:
        return text
    result = normalize_spelling(text)
    for pattern, repl in _CLEANUP_PATTERNS:
        result = pattern.sub(repl, result)
    # Dọn khoảng trắng dư ra trước dấu ":" sau khi xóa ngoặc đơn
    result = re.sub(r"[ \t]+:", ":", result)
    return result


def normalize_spelling(text: str) -> str:
    """
    Chuẩn hóa các biến thể chính tả phổ biến trong văn bản tiếng Việt y khoa.
    An toàn để gọi nhiều lần (idempotent) và gọi trên text rỗng/None.
    """
    if not text:
        return text
    result = text
    for pattern, repl in _COMPILED:
        result = pattern.sub(repl, result)
    return result
