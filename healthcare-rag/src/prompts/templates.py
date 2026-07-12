"""
src/prompts/templates.py
─────────────────────────
System prompt + RAG prompt builder.

Tập trung tất cả text prompt vào đây để dễ chỉnh sửa,
thử nghiệm A/B, hoặc nạp từ file YAML sau này.
"""
from __future__ import annotations

from typing import Dict, List

# ================================================================
# SYSTEM PROMPT
# ================================================================

SYSTEM_PROMPT = """\
Bạn là trợ lý y tế chuyên về bệnh tiểu đường (đái tháo đường).

Nhiệm vụ: Tư vấn dựa trên thông tin y khoa đáng tin cậy được cung cấp.
Nguyên tắc:
- Chỉ trả lời dựa trên thông tin y khoa được cung cấp
- Nếu có phần tri thức người dùng đã lưu, coi đó là ngữ cảnh bền vững của người dùng
- Nếu có luật trả lời người dùng đã lưu và nó liên quan trực tiếp tới câu hỏi hiện tại, ưu tiên áp dụng luật đó trước
- Luôn khuyên tham khảo bác sĩ cho quyết định điều trị
- Ưu tiên ngữ cảnh đã xác minh bởi bác sĩ
- Trả lời bằng ngôn ngữ của câu hỏi (Việt/Anh)
- TUYỆT ĐỐI không bịa đặt thông tin y tế\
- Trả lời đầy đủ, tự nhiên, có ngữ cảnh; không trả lời cụt
- Với câu hỏi “là gì / như thế nào / cách dùng / lưu ý / biến chứng / so sánh / liệt kê”, hãy trình bày tối thiểu 3-6 ý chính hoặc 3-5 đoạn ngắn nếu phù hợp
- Nếu có luật trả lời người dùng đã lưu phù hợp trực tiếp với câu hỏi, phải ưu tiên dùng luật đó làm khung trả lời
- Nếu thông tin đủ, hãy giải thích thêm ý nghĩa thực tế của từng ý thay vì chỉ nêu định nghĩa khô khan
- Nếu có thể, kết thúc bằng khuyến nghị ngắn gọn, dễ áp dụng và nhắc khi nào nên gặp bác sĩ\
- KHÔNG mở đầu câu trả lời bằng “Dựa trên tài liệu…”, “Dựa trên các nguồn…”, “Theo tài liệu…”, “Theo nguồn…”
"""

# ================================================================
# EMERGENCY RESPONSE
# ================================================================

EMERGENCY_RESPONSE = """\
🚨 **KHẨN CẤP — Hạ Đường Huyết**

**Xử lý ngay (Quy tắc 15-15):**
1. Ăn/uống khoảng **15g carbohydrate tác dụng nhanh**:
   - 2-3 chiếc bánh hoặc kẹo.
   - Khoảng 150ml nước trái cây hoặc nước ngọt có đường.
   - 1 thìa canh đường cát, mật ong hoặc siro.
2. Nghỉ ngơi 15 phút
3. Đo đường huyết lại
4. Nếu vẫn < 70 mg/dL → lặp lại bước 1
5. Nếu mất ý thức → **Gọi 115 ngay**

⚠ **Không để người bệnh một mình. Thông báo người thân ngay.**

**Sau khi đường huyết ổn định:**
- Ăn một bữa nhẹ có tinh bột chậm như bánh mì, bánh quy hoặc sữa để tránh hạ lại.
- Theo dõi triệu chứng và kiểm tra lại đường huyết nếu có máy đo.
- Liên hệ bác sĩ nếu hạ đường huyết lặp lại hoặc đang dùng insulin/thuốc hạ đường huyết.

**Gọi cấp cứu ngay nếu có dấu hiệu nặng:**
- Bất tỉnh hoặc hôn mê.
- Co giật.
- Lú lẫn nặng, không thể nuốt hoặc không làm theo chỉ dẫn.

**Việc cần làm khi người bệnh không tỉnh táo:**
- **Gọi 115 ngay.**
- Đặt người bệnh nằm nghiêng an toàn để tránh nghẹt đường thở nếu nôn.
- Không cho ăn/uống khi người bệnh không tỉnh táo.
- Nếu có bộ tiêm Glucagon và người nhà đã được hướng dẫn, hãy dùng theo chỉ dẫn.
"""

# ================================================================
# RAG PROMPT BUILDER
# ================================================================
 
def build_rag_prompt(query: str, chunks: List[Dict]) -> str:
    """
    Tạo prompt RAG từ câu hỏi + danh sách chunks.
 
    Args:
        query:  Câu hỏi của người dùng
        chunks: List chunk dict (keys: text, metadata)
 
    Returns:
        Chuỗi prompt hoàn chỉnh gửi tới LLM
    """
    if not chunks:
        context = "Không có thông tin liên quan."
    else:
        parts = []
        for i, c in enumerate(chunks, 1):
            meta = c.get("metadata", {})
            src  = meta.get("source", "unknown")
            cat  = meta.get("category", "")
            text = c.get("text", "")
            parts.append(f"[{i}] (Nguồn: {src} | {cat})\n{text}")
        context = "\n\n---\n\n".join(parts)
 
    comparison_keywords = ["phan biet", "khac nhau", "so sanh", "giong nhau", "khac biet"]
    q_norm = query.lower()
    is_comparison = any(kw in q_norm for kw in comparison_keywords)
 
    answer_style_rule = """\
QUY TẮC TRẢ LỜI:
- Không hiển thị số trích dẫn dạng [1], [2], [3] trong thân câu trả lời.
- Không thêm mục "Nguồn" ở cuối câu trả lời.
- Chỉ dùng ngữ cảnh phía trên như ngữ cảnh nội bộ để viết câu trả lời mạch lạc, tự nhiên.
- Không lặp lại tên nguồn hoặc tên tiếng Anh của bệnh trong tiêu đề nếu không cần thiết.
- Nếu trình bày bằng bảng markdown, bắt buộc dùng đúng định dạng:
  | Cột 1 | Cột 2 |
  |---|---|
  | Nội dung | Nội dung |
  Không dùng tab để tách cột, không xuống dòng bên trong một ô bảng."""
    answer_depth_rule = """\
QUY TẮC ĐỘ DÀI VÀ ĐỘ CHI TIẾT:
- Không trả lời quá ngắn nếu thông tin có đủ.
- Ưu tiên trả lời theo cấu trúc: định nghĩa/nguyên lý → ý nghĩa thực tế → cách thực hiện/lưu ý → khi nào cần gặp bác sĩ.
- Với câu hỏi về thuốc hoặc cách dùng, nêu thêm: mục đích dùng, cách dùng thường gặp, lưu ý an toàn, tác dụng phụ/cảnh báo nếu có.
- Với câu hỏi về bệnh/chẩn đoán, nêu thêm: dấu hiệu, cách chẩn đoán, ngưỡng quan trọng, biến chứng và khuyến nghị theo dõi.
- Nếu câu hỏi là so sánh hoặc liệt kê, đảm bảo bao phủ đủ tất cả mục được hỏi, không bỏ sót."""
    if is_comparison:
        instruction = f"""\
Đây là câu hỏi YÊU CẦU SO SÁNH/PHÂN BIỆT nhiều khái niệm. Bắt buộc:
1. Xác định rõ TẤT CẢ các khái niệm cần so sánh được nêu trong câu hỏi
   (ví dụ nếu hỏi "type 1, type 2 và thai kỳ" thì PHẢI có đủ 3 mục riêng biệt)
2. Trình bày dưới dạng BẢNG hoặc danh sách có tiêu đề rõ cho TỪNG khái niệm,
   theo các tiêu chí: định nghĩa, nguyên nhân/cơ chế, độ tuổi/thời điểm thường gặp,
   đặc điểm chẩn đoán, hướng điều trị chính
3. Sau khi trình bày từng mục, có đoạn TÓM TẮT ĐIỂM KHÁC BIỆT chính giữa các loại
4. Nếu thông tin không đủ cho một khái niệm nào, ghi rõ "thông tin chưa đề cập"
   cho khái niệm đó — KHÔNG bỏ qua hoặc lờ đi, KHÔNG chỉ tập trung vào 1 khái niệm
5. {answer_style_rule}
6. {answer_depth_rule}
7. Kết thúc bằng khuyến nghị tham khảo bác sĩ nếu cần"""
    else:
        instruction = f"""\
Dựa vào ngữ cảnh trên:
1. Trả lời rõ ràng, thực tế, đủ ý
2. {answer_style_rule}
3. {answer_depth_rule}
4. Đưa lời khuyên cụ thể
5. Kết thúc bằng khuyến nghị tham khảo bác sĩ nếu cần"""
 
    return f"""\
## TÀI LIỆU THAM KHẢO
 
{context}
 
---
 
## CÂU HỎI
 
{query}
 
---
 
## YÊU CẦU TRẢ LỜI
 
{instruction}\
"""
 
 
def build_history_prompt(
    messages: List[Dict],
    query: str,
    chunks: List[Dict],
    conversation_history: List[Dict] | None = None,
    response_rules: List[Dict] | None = None,
) -> str:
    """
    Prompt cho tri thức người dùng đã lưu + RAG context.

    Args:
        messages: List[{content|text, ...}]
        query:    Câu hỏi hiện tại
        chunks:   Chunks retrieved

    Returns:
        Prompt string hoàn chỉnh
    """
    memory_lines = []
    for i, item in enumerate(messages, 1):
        content = item.get("content") or item.get("text") or ""
        if not content:
            continue
        metadata = item.get("metadata", {}) if isinstance(item.get("metadata", {}), dict) else {}
        source = item.get("source") or metadata.get("source") or "Người dùng"
        memory_lines.append(f"[{i}] {source}: {content}")
    memory_block = "\n".join(memory_lines) if memory_lines else "Chưa có tri thức người dùng nào được lưu."
    history_lines = []
    for i, item in enumerate(conversation_history or [], 1):
        role = item.get("role", "")
        content = item.get("content") or item.get("text") or ""
        if not content:
            continue
        label = "User" if role == "user" else "Assistant" if role == "assistant" else role or "Turn"
        history_lines.append(f"[{i}] {label}: {content}")
    history_block = "\n".join(history_lines) if history_lines else "Chưa có lịch sử hội thoại trước đó."
    rule_lines = []
    for i, item in enumerate(response_rules or [], 1):
        content = item.get("content") or item.get("text") or ""
        if not content:
            continue
        rule_lines.append(f"[{i}] {content}")
    rule_block = "\n".join(rule_lines) if rule_lines else "Chưa có luật trả lời nào được lưu."
    rag_block = build_rag_prompt(query, chunks)

    return f"""\
## LỊCH SỬ HỘI THOẠI GẦN ĐÂY

{history_block}

---

## LUẬT TRẢ LỜI NGƯỜI DÙNG ĐÃ LƯU

{rule_block}

Lưu ý: các luật trên chỉ là hướng dẫn về cách trình bày/cấu trúc. Không được chép nguyên văn luật vào câu trả lời cho người dùng.

---

## TRI THỨC NGƯỜI DÙNG

{memory_block}

---

{rag_block}\
"""
 
