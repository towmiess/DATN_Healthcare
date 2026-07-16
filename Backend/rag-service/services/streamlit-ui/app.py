"""
Streamlit UI — Healthcare RAG v2
==================================
Cập nhật:
- Chế độ chat ngắn gọn, tập trung vào tri thức người dùng và tài liệu có sẵn
- Câu hỏi gợi ý theo chủ đề sau mỗi câu trả lời (Suggested Followups)
- Màn hình chào ban đầu với câu hỏi thường gặp theo chủ đề
- Fix chat_input bar responsive đúng chiều rộng
"""

import streamlit as st
import requests
import os
import uuid
import time
import html
import re
from urllib.parse import urlparse
from pathlib import Path

RAG_API_URL      = os.getenv("RAG_API_URL", "http://localhost:8000")
REQUEST_TIMEOUT  = int(os.getenv("RAG_API_TIMEOUT_S", 300))
ADMIN_TOKEN      = os.getenv("ADMIN_SECRET_KEY", "healthcare-admin-dev")

_candidates = [
    Path("/app/data/pdfs"),
    Path(__file__).parent.parent.parent / "data" / "pdfs",
    Path(__file__).parent.parent / "data" / "pdfs",
]
PDF_DIR = next((p for p in _candidates if p.exists()), _candidates[0])
PDF_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(
    page_title="🏥 Tư Vấn Tiểu Đường",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Be Vietnam Pro', sans-serif; }

  /* ── Chat input: responsive, không đè sidebar ── */
  div[data-testid="stChatInput"] {
      position: fixed !important;
      bottom: 0 !important;
      left: var(--sidebar-width, 21rem) !important;
      right: 0 !important;
      width: auto !important;
      max-width: none !important;
      transform: none !important;
      padding: 0.75rem 2rem 1rem 2rem !important;
      background: var(--background-color, #ffffff) !important;
      border-top: 1px solid #e2e8f0 !important;
      z-index: 999 !important;
  }
  div[data-testid="stChatInput"] > div {
      max-width: 860px;
      margin: 0 auto;
  }
  .main .block-container { padding-bottom: 7rem; }

  /* ── Header ── */
  .rag-header {
    background: linear-gradient(135deg, #1e3a8a 0%, #0369a1 100%);
    color: white; padding: 20px 28px; border-radius: 16px; margin-bottom: 16px;
    display: flex; align-items: center; gap: 16px;
  }
  .rag-header h1 { font-size: 22px; font-weight: 700; margin: 0; }
  .rag-header p  { font-size: 13px; opacity: 0.85; margin: 4px 0 0; }

  /* ── Suggested followups ── */
  .followup-box {
    margin: 12px 0 4px 0;
    border: 1px solid #e0e7ff;
    border-radius: 12px;
    background: #f8faff;
    padding: 12px 16px;
  }
  .followup-title {
    font-size: 12px; font-weight: 600; color: #6366f1;
    display: flex; align-items: center; gap: 6px; margin-bottom: 8px;
  }
  .followup-item {
    display: flex; align-items: center; justify-content: space-between;
    padding: 7px 12px; margin: 4px 0;
    background: white; border: 1px solid #e2e8f0; border-radius: 8px;
    cursor: pointer; font-size: 13px; color: #1e293b; transition: all 0.15s;
  }
  .followup-item:hover { background: #eef2ff; border-color: #6366f1; }

  /* ── Welcome screen topic cards ── */
  .welcome-section { margin: 24px 0 8px; }
  .welcome-title { font-size: 14px; font-weight: 700; color: #374151; margin-bottom: 10px; }
  .topic-card {
    background: white; border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 14px 16px; margin-bottom: 8px;
    transition: box-shadow 0.15s;
  }
  .topic-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
  .topic-label { font-size: 13px; font-weight: 600; color: #1e293b; margin-bottom: 6px; }
  .topic-q { font-size: 12px; color: #4f46e5; cursor: pointer;
    padding: 3px 0; display: flex; align-items: center; gap: 4px; }

  /* ── Others ── */
  .cat-card {
    background: white; border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 14px 18px; margin: 6px 0; display: flex;
    align-items: center; justify-content: space-between;
  }
  .cat-name  { font-weight: 600; font-size: 14px; color: #1e293b; }
  .cat-count { font-size: 12px; color: #64748b; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
  .badge-ok   { background: #dcfce7; color: #16a34a; }
  .badge-warn { background: #fef9c3; color: #ca8a04; }
  .badge-none { background: #f1f5f9; color: #94a3b8; }
  .stat-box {
    background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
    border: 1px solid #bae6fd; border-radius: 12px;
    padding: 16px 20px; text-align: center; margin-bottom: 8px;
  }
  .stat-num   { font-size: 28px; font-weight: 700; color: #0369a1; }
  .stat-label { font-size: 12px; color: #64748b; margin-top: 4px; }
  .sidebar-section { background: #f8fafc; border-radius: 10px; padding: 12px; margin-bottom: 12px; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════

def get_api_health():
    try:
        r = requests.get(f"{RAG_API_URL}/health", timeout=4)
        return r.json()
    except Exception:
        return None


def admin_headers() -> dict:
    return {"X-Admin-Token": ADMIN_TOKEN}


def normalize_sources(sources):
    normalized = []
    for item in sources or []:
        if isinstance(item, dict):
            if item.get("category") in {"user_knowledge", "user_response_rule"}:
                continue
            url = item.get("url", "") or item.get("source_url", "")
            title = item.get("title", "") or item.get("document_title", "") or item.get("source", "")
            normalized.append({
                "source": item.get("source", ""),
                "title": title,
                "url": url,
                "filename": item.get("filename", ""),
                "category": item.get("category", ""),
                "similarity": item.get("similarity", 0.0),
            })
        else:
            normalized.append({
                "source": str(item),
                "title": str(item),
                "url": "",
                "filename": "",
                "category": "",
                "similarity": 0.0,
            })
    return normalized


def source_label(source: dict, max_length: int = 34) -> str:
    url = source.get("url") or ""
    label = source.get("title") or source.get("source") or ""
    if not label and url:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "") or parsed.path.split("/")[0]
            label = domain or "Nguồn"
        except Exception:
            label = "Nguồn"
    elif not label and source.get("filename"):
        label = source["filename"]
    elif not label:
        label = "Nguồn"
    return label if len(label) <= max_length else f"{label[:max_length - 1]}…"


def _is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and s.count("|") >= 2


def _is_table_separator(line: str) -> bool:
    s = line.strip().strip("|")
    cells = [c.strip() for c in s.split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells)


def _render_html_table(header_cells, body_rows, inline_fmt) -> str:
    ths = "".join(f'<th style="padding:8px 10px;border:1px solid #dbe4ff;background:#eef4ff;'
                  f'text-align:left;font-size:13px;">{inline_fmt(html.escape(c.strip()))}</th>'
                  for c in header_cells)
    trs = []
    for row in body_rows:
        tds = "".join(f'<td style="padding:8px 10px;border:1px solid #e2e8f0;font-size:13px;">'
                      f'{inline_fmt(html.escape(c.strip()))}</td>' for c in row)
        trs.append(f"<tr>{tds}</tr>")
    return (
        '<table style="border-collapse:collapse;width:100%;margin:10px 0;">'
        f"<thead><tr>{ths}</tr></thead><tbody>{''.join(trs)}</tbody></table>"
    )


def format_answer_text(text: str) -> str:
    if not text:
        return ""

    important_prefixes = (
        "lưu ý:",
        "lưu ý quan trọng:",
        "quan trọng:",
        "cảnh báo:",
        "khuyến nghị:",
        "chống chỉ định:",
        "thận trọng:",
    )
    heading_prefixes = (
        "định nghĩa",
        "công dụng",
        "liều dùng",
        "tác dụng phụ",
        "lưu ý",
        "khuyến nghị",
        "cảnh báo",
        "chống chỉ định",
        "tương tác",
        "chỉ định",
        "cơ chế hoạt động",
        "lời khuyên",
        "điều quan trọng",
        "thành phần",
        "dinh dưỡng",
        "tác dụng",
    )
    # Cụm từ cảnh báo/quan trọng xuất hiện Ở BẤT KỲ ĐÂU trong câu (không chỉ đầu dòng)
    # → in đậm + đỏ ngay tại chỗ, không cần cả dòng phải bắt đầu bằng cụm đó.
    inline_warning_pattern = re.compile(
        r"(không nên|không được|tránh(?:\s+dùng|\s+ăn)?|nguy hiểm|nguy cơ cao|"
        r"chống chỉ định|thận trọng|cảnh báo|khẩn cấp|cần đi khám ngay|"
        r"gọi (?:cấp cứu|115) ngay|tuyệt đối không|quá liều|tác dụng phụ nghiêm trọng|"
        r"phải tham khảo bác sĩ|hãy tham khảo bác sĩ)",
        flags=re.IGNORECASE,
    )
    # Từ khóa y khoa/dinh dưỡng chính — in đậm để dễ quét thông tin
    highlight_pattern = re.compile(
        r"\b(HbA1c|Metformin|Insulin|Aspirin|Glucophage|Mixtard|Atoris|"
        r"tiểu đường|đái tháo đường|hạ đường huyết|tăng đường huyết|đường huyết|"
        r"tim mạch|thận|võng mạc|mắt|bàn chân|thần kinh ngoại biên|"
        r"chỉ số đường huyết|GI|GL|calo|protein|đạm|chất béo|carbohydrate|carb|"
        r"chất xơ|đường|natri|kali|canxi|sắt|vitamin\s*[A-Za-z0-9]*|omega-3|"
        r"cholesterol|huyết áp|kháng insulin|type\s*1|type\s*2|thai kỳ)\b",
        flags=re.IGNORECASE,
    )

    def _inline_fmt(escaped: str) -> str:
        """Áp dụng bold cảnh báo (đỏ) + bold từ khóa lên text ĐÃ escape."""
        escaped = inline_warning_pattern.sub(
            lambda m: f'<span style="color:#dc2626;font-weight:700;">{m.group(0)}</span>',
            escaped,
        )
        return highlight_pattern.sub(r"<b>\1</b>", escaped)

    def _strip_leading_marker(text: str) -> str:
        cleaned = text.strip()
        while True:
            next_cleaned = re.sub(r"^[\s\u200b\ufeff]*(?:\d+[.)]|[*•\-])\s+", "", cleaned).strip()
            if next_cleaned == cleaned:
                return cleaned
            cleaned = next_cleaned

    raw_lines = text.splitlines()
    formatted_lines = []
    list_items = []
    current_parent = None

    def flush_list():
        nonlocal list_items, current_parent
        if list_items:
            rendered_items = []
            for index, item in enumerate(list_items, 1):
                children = item.get("children") or []
                if children:
                    rendered_items.append(
                        "<li style='margin:0.04rem 0;line-height:1.5;'>"
                        f"<strong>{index}. {item['text']}</strong>"
                        "<ul style='margin:0.12rem 0 0.18rem 1rem;padding-left:1rem;list-style-type:disc;'>"
                        + "".join(
                            f"<li style='margin:0.03rem 0;line-height:1.45;'>{child}</li>"
                            for child in children
                        )
                        + "</ul></li>"
                    )
                else:
                    rendered_items.append(
                        f"<li style='margin:0.04rem 0;line-height:1.5;'><strong>{index}.</strong> {item['text']}</li>"
                    )
            formatted_lines.append(
                "<ol style='margin:0.12rem 0 0.22rem 1.15rem;padding-left:1rem;list-style-position:outside;'>"
                + "".join(rendered_items)
                + "</ol>"
            )
            list_items = []
            current_parent = None

    bullet_pattern = re.compile(
        r"^[\s\u200b\ufeff]*([*•\-]|(?:\d+[.)]))\s+(.+)$"
    )

    i = 0
    n = len(raw_lines)
    while i < n:
        raw_line = raw_lines[i]
        line = raw_line.strip()

        # ── Phát hiện bảng markdown: dòng header | dòng --- | các dòng dữ liệu ──
        if (_is_table_row(line) and i + 1 < n
                and _is_table_separator(raw_lines[i + 1])):
            header_cells = line.strip().strip("|").split("|")
            j = i + 2
            body_rows = []
            while j < n and _is_table_row(raw_lines[j].strip()):
                body_rows.append(raw_lines[j].strip().strip("|").split("|"))
                j += 1
            formatted_lines.append(_render_html_table(header_cells, body_rows, _inline_fmt))
            i = j
            continue

        if not line:
            next_nonempty = ""
            for k in range(i + 1, n):
                candidate = raw_lines[k].strip()
                if candidate:
                    next_nonempty = candidate
                    break
            if current_parent is not None and bullet_pattern.match(next_nonempty):
                i += 1
                continue
            flush_list()
            formatted_lines.append("")
            i += 1
            continue

        lower = line.lower()
        if any(lower.startswith(prefix) for prefix in important_prefixes):
            flush_list()
            formatted_lines.append(
                f'<span style="color:#dc2626;font-weight:700;">{html.escape(line)}</span>'
            )
            i += 1
            continue

        if lower.startswith("luôn tham khảo ý kiến bác sĩ"):
            flush_list()
            formatted_lines.append(f"**{html.escape(line)}**")
            i += 1
            continue

        if any(lower == prefix or lower.startswith(prefix + " ") for prefix in heading_prefixes):
            flush_list()
            formatted_lines.append(f"**{html.escape(line)}**")
            i += 1
            continue

        bullet_match = bullet_pattern.match(raw_line)
        if bullet_match:
            escaped = html.escape(_strip_leading_marker(bullet_match.group(2).strip()))
            escaped = inline_warning_pattern.sub(
                lambda m: f'<span style="color:#dc2626;font-weight:700;">{m.group(0)}</span>',
                escaped,
            )
            escaped = highlight_pattern.sub(r"<b>\1</b>", escaped)
            is_parent_item = escaped.rstrip().endswith(":")
            if is_parent_item:
                parent_item = {"text": escaped, "children": []}
                list_items.append(parent_item)
                current_parent = parent_item
            elif current_parent is not None:
                current_parent["children"].append(escaped)
            else:
                list_items.append({"text": escaped, "children": []})
            i += 1
            continue

        escaped = html.escape(line)
        # 1. Bôi đỏ+đậm cụm cảnh báo xuất hiện giữa câu trước
        escaped = inline_warning_pattern.sub(
            lambda m: f'<span style="color:#dc2626;font-weight:700;">{m.group(0)}</span>',
            escaped,
        )
        # 2. Rồi mới in đậm từ khóa y khoa/dinh dưỡng thông thường (không đè lên span đỏ ở trên
        #    vì highlight_pattern không khớp bên trong thẻ style/color đã có sẵn dấu ";")
        escaped = highlight_pattern.sub(r"<b>\1</b>", escaped)
        flush_list()
        formatted_lines.append(escaped)
        i += 1

    flush_list()
    return "<br>".join(formatted_lines)


def render_source_cards(sources):
    for index, source in enumerate(sources, 1):
        title = source.get("title") or source.get("source") or f"Nguồn {index}"
        url = source.get("url") or ""
        safe_title = html.escape(title)
        safe_url = html.escape(url)

        # Có thể bật lại phần category/similarity/chunk nếu cần debug sau này.
        if url:
            link_html = f'<a href="{safe_url}" target="_blank" style="color:#2563eb;text-decoration:underline;">{safe_url}</a>'
        else:
            link_html = ""

        st.markdown(
            f"""
            <div style="border:1px solid #dbe4ff;border-radius:12px;padding:12px 14px;margin-bottom:10px;background:#f8fbff;">
              <div style="font-weight:700;margin-bottom:6px;color:#0f172a;">{safe_title}</div>
              {f'<div style="font-size:12px;word-break:break-all;">{link_html}</div>' if link_html else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )


def open_source_modal(sources):
    st.session_state.source_modal_sources = normalize_sources(sources)
    st.session_state.source_modal_request_id = uuid.uuid4().hex
    st.session_state.source_modal_open = True


def render_source_modal():
    sources = st.session_state.get("source_modal_sources") or []
    request_id = st.session_state.get("source_modal_request_id")
    if not st.session_state.get("source_modal_open") or not sources:
        return

    st.session_state.source_modal_open = False
    st.session_state.source_modal_sources = []
    st.session_state.source_modal_request_id = None

    def _body():
        # Chunk count/source stats intentionally hidden in popup.
        render_source_cards(sources)
        close_key = f"close_source_modal_{request_id or 'default'}"
        if st.button("Đóng", key=close_key):
            st.rerun()

    dialog_fn = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)
    if dialog_fn:
        @dialog_fn("Sources")
        def _dialog():
            _body()
        _dialog()
    else:
        with st.expander("Sources", expanded=True):
            _body()


def count_pdfs_by_category() -> dict:
    counts = {}
    if not PDF_DIR.exists():
        return counts
    for f in PDF_DIR.rglob("*"):
        if f.is_file() and f.suffix in (".pdf", ".txt") and not f.name.startswith("."):
            try:
                rel = f.relative_to(PDF_DIR)
                folder = str(rel.parent) if str(rel.parent) != "." else "(root)"
            except ValueError:
                folder = "(root)"
            counts[folder] = counts.get(folder, 0) + 1
    return counts


def get_all_files_flat() -> list:
    files = []
    if not PDF_DIR.exists():
        return files
    for f in sorted(PDF_DIR.rglob("*.pdf")) + sorted(PDF_DIR.rglob("*.txt")):
        if not f.name.startswith("."):
            try:
                rel = f.relative_to(PDF_DIR)
                folder = "/".join(rel.parts[:-1]) if len(rel.parts) > 1 else "(root)"
                files.append({"path": f, "name": f.name, "folder": folder,
                               "size_kb": f.stat().st_size // 1024, "ext": f.suffix})
            except Exception:
                pass
    return files


def call_admin_rebuild() -> str:
    try:
        resp = requests.post(f"{RAG_API_URL}/admin/rebuild-index",
                              headers=admin_headers(), timeout=600)
        if resp.status_code == 200:
            return str(resp.json())
        return f"❌ {resp.status_code}: {resp.text[:300]}"
    except requests.exceptions.Timeout:
        return "⏱ Timeout — rebuild đang chạy nền, đợi vài phút rồi reload"
    except Exception as e:
        return f"❌ {e}"


# ══════════════════════════════════════════════════════════
# Suggested followup questions (topic-based)
# ══════════════════════════════════════════════════════════

TOPIC_FOLLOWUPS = {
    "chẩn đoán": [
        "HbA1c bao nhiêu là bị tiểu đường?",
        "Xét nghiệm đường huyết lúc đói bình thường là bao nhiêu?",
        "Tiền tiểu đường có cần điều trị không?",
    ],
    "chế độ ăn": [
        "Người tiểu đường nên ăn bao nhiêu tinh bột mỗi ngày?",
        "Trái cây nào người tiểu đường ăn được?",
        "Chỉ số GI (glycemic index) là gì?",
    ],
    "thuốc": [
        "Metformin có tác dụng phụ gì không?",
        "Khi nào cần dùng insulin?",
        "Thuốc tiểu đường uống lúc nào là tốt nhất?",
    ],
    "biến chứng": [
        "Tiểu đường ảnh hưởng đến thận như thế nào?",
        "Biến chứng mắt của tiểu đường có chữa được không?",
        "Bệnh thần kinh ngoại biên do tiểu đường là gì?",
    ],
    "hạ đường huyết": [
        "Triệu chứng hạ đường huyết là gì?",
        "Khi hạ đường huyết nên ăn gì để tăng nhanh?",
        "Làm sao phòng ngừa hạ đường huyết ban đêm?",
    ],
    "lối sống": [
        "Người tiểu đường nên tập thể dục như thế nào?",
        "Stress ảnh hưởng đến đường huyết không?",
        "Người tiểu đường có uống rượu bia được không?",
    ],
    "mặc định": [
        "Tiểu đường type 1 khác type 2 như thế nào?",
        "Khi nào cần đi khám tiểu đường ngay?",
        "Tự theo dõi đường huyết tại nhà như thế nào?",
    ],
}

def get_followups(question: str) -> list:
    """Chọn câu hỏi gợi ý dựa trên từ khóa trong câu hỏi của người dùng."""
    q = question.lower()
    if any(w in q for w in ["hba1c", "xét nghiệm", "chẩn đoán", "đường huyết", "glucose"]):
        return TOPIC_FOLLOWUPS["chẩn đoán"]
    if any(w in q for w in ["ăn", "thực phẩm", "diet", "phở", "cơm", "trái cây", "đường"]):
        return TOPIC_FOLLOWUPS["chế độ ăn"]
    if any(w in q for w in ["thuốc", "metformin", "insulin", "uống", "tiêm"]):
        return TOPIC_FOLLOWUPS["thuốc"]
    if any(w in q for w in ["biến chứng", "thận", "mắt", "tim", "thần kinh", "võng mạc"]):
        return TOPIC_FOLLOWUPS["biến chứng"]
    if any(w in q for w in ["hạ đường", "hypoglycemia", "chóng mặt", "run"]):
        return TOPIC_FOLLOWUPS["hạ đường huyết"]
    if any(w in q for w in ["tập", "thể dục", "vận động", "stress", "rượu", "bia", "ngủ"]):
        return TOPIC_FOLLOWUPS["lối sống"]
    return TOPIC_FOLLOWUPS["mặc định"]


# ══════════════════════════════════════════════════════════
# Welcome screen topics (FAQ)
# ══════════════════════════════════════════════════════════

WELCOME_TOPICS = [
    {
        "icon": "🩺",
        "label": "Chẩn đoán & Xét nghiệm",
        "questions": [
            "HbA1c bao nhiêu là cần điều trị?",
            "Tiểu đường có thể chẩn đoán tại nhà không?",
        ],
    },
    {
        "icon": "🍚",
        "label": "Chế độ ăn uống",
        "questions": [
            "Người tiểu đường type 2 ăn phở được không?",
            "Thực đơn 1 ngày cho người tiểu đường?",
        ],
    },
    {
        "icon": "💊",
        "label": "Thuốc & Điều trị",
        "questions": [
            "Metformin uống lúc nào tốt nhất?",
            "Khi nào cần chuyển sang dùng insulin?",
        ],
    },
    {
        "icon": "⚠️",
        "label": "Biến chứng",
        "questions": [
            "Biến chứng tim mạch của tiểu đường?",
            "Tiểu đường có ảnh hưởng đến thận không?",
        ],
    },
    {
        "icon": "🏃",
        "label": "Lối sống & Phòng ngừa",
        "questions": [
            "Người tiểu đường nên tập thể dục gì?",
            "Làm sao phòng ngừa tiền tiểu đường?",
        ],
    },
    {
        "icon": "🚨",
        "label": "Xử lý khẩn cấp",
        "questions": [
            "Hạ đường huyết phải làm gì?",
            "Dấu hiệu tăng đường huyết nguy hiểm?",
        ],
    },
]


# ══════════════════════════════════════════════════════════
# Session state
# ══════════════════════════════════════════════════════════

defaults = {
    "session_id": str(uuid.uuid4()),
    "messages": [],
    "rebuild_log": "",
    "remember_knowledge": False,
    "source_modal_open": False,
    "source_modal_sources": [],
    "source_modal_request_id": None,
    "show_followups_for": -1,   # index tin nhắn assistant cuối hiện followups
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### 🏥 Healthcare RAG ")
    health = get_api_health()
    if health:
        icon = "🟢" if health.get("rag_ready") else "🟡"
        st.markdown(f"""
        <div class="sidebar-section">
          <b>{icon} API Online</b><br>
          <small>
            📦 {health.get('total_chunks', 0):,} chunks<br>
            💾 {health.get('session_store', 'N/A')}<br>
            🔗 <code>{st.session_state.session_id[:8]}…</code>
          </small>
        </div>""", unsafe_allow_html=True)
        if not health.get("rag_ready"):
            st.warning("⚠ RAG chưa sẵn sàng — chạy `python scripts/ingest.py` rồi restart rag-api")
    else:
        st.markdown('<div class="sidebar-section">🔴 <b>API Offline</b><br><small>docker-compose up -d</small></div>',
                    unsafe_allow_html=True)

    st.divider()

    st.checkbox(
        "🧠 Ghi nhớ câu này",
        key="remember_knowledge",
        help="Bật để lưu tin nhắn hiện tại vào bộ nhớ tri thức.",
    )
    st.caption("Mẹo: bắt đầu tin nhắn bằng `/nho` hoặc `nhớ rằng ...` để lưu ngay.")

    # ── Nút tạo chat mới ──
    if st.button("✏️ Chat mới", use_container_width=True, type="primary"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.show_followups_for = -1
        try:
            requests.delete(f"{RAG_API_URL}/chat/session/{st.session_state.session_id}", timeout=5)
        except Exception:
            pass
        st.rerun()

    st.divider()

    # ── Câu hỏi mẫu ──
    st.markdown("**📋 Câu hỏi mẫu**")
    examples = [
        "HbA1c bao nhiêu là cần điều trị?",
        "Metformin uống lúc nào tốt nhất?",
        "Tiểu đường có ảnh hưởng đến thận không?",
        "Hạ đường huyết phải làm gì?",
        "Phân biệt tiểu đường type 1, type 2 và thai kỳ",
        "Biến chứng tim mạch của tiểu đường?",
    ]
    for idx, ex in enumerate(examples):
        if st.button(ex, use_container_width=True, key=f"ex_btn_{idx}"):
            st.session_state._example_query = ex
            st.rerun()

    st.divider()
    if st.button("🗑 Xóa chat hiện tại", use_container_width=True):
        try:
            requests.delete(f"{RAG_API_URL}/chat/session/{st.session_state.session_id}", timeout=5)
        except Exception:
            pass
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.show_followups_for = -1
        st.rerun()


# ══════════════════════════════════════════════════════════
# MAIN TABS
# ══════════════════════════════════════════════════════════

tab_chat, tab_crawler, tab_docs, tab_stats = st.tabs(
    ["💬 Chat", "🕷 Crawler", "📚 Tài liệu", "📊 Thống kê"]
)


# ═══════════════════════════════════════════════════════════
# TAB 1 — CHAT
# ═══════════════════════════════════════════════════════════
with tab_chat:
    st.markdown("""
    <div class="rag-header">
      <span style="font-size:36px">🏥</span>
      <div>
        <h1>Chatbot Tư Vấn Tiểu Đường</h1>
        <p>Dựa trên ADA Standards of Care 2026 & tài liệu y khoa Việt Nam</p>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── Màn hình chào (chỉ hiện khi chưa có tin nhắn nào) ──
    if not st.session_state.messages:
        st.markdown("""
        <div style="text-align:center; padding: 12px 0 8px;">
          <div style="font-size:40px">👋</div>
          <div style="font-size:18px; font-weight:700; color:#1e293b; margin-top:6px;">
            Xin chào! Tôi có thể giúp gì cho bạn?
          </div>
          <div style="font-size:13px; color:#64748b; margin-top:4px;">
            Hỏi về tiểu đường, biến chứng, thuốc, chế độ ăn và nhiều hơn nữa.
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Topic cards dạng 2 cột
        cols = st.columns(2)
        for i, topic in enumerate(WELCOME_TOPICS):
            with cols[i % 2]:
                with st.container():
                    st.markdown(f"""
                    <div style="background:white; border:1px solid #e2e8f0; border-radius:12px;
                         padding:12px 16px; margin-bottom:8px;">
                      <div style="font-size:13px; font-weight:700; color:#1e293b; margin-bottom:6px;">
                        {topic['icon']} {topic['label']}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                    for q in topic["questions"]:
                        if st.button(
                            f"→ {q}",
                            key=f"welcome_q_{i}_{q[:20]}",
                            use_container_width=True,
                        ):
                            st.session_state._example_query = q
                            st.rerun()

    # ── Render lịch sử tin nhắn ──
    msgs = st.session_state.messages
    for msg_idx, msg in enumerate(msgs):
        avatar = "👤" if msg["role"] == "user" else "🏥"
        with st.chat_message(msg["role"], avatar=avatar):
            if msg["role"] == "assistant":
                st.markdown(format_answer_text(msg["content"]), unsafe_allow_html=True)
            else:
                st.markdown(msg["content"])
            meta = msg.get("meta")
            if meta:
                c1, c2, c3 = st.columns([1, 1, 0.85])
                c1.caption(f"⏱ {meta.get('ms', 0):,}ms")

                route_icons = {
                    "drug": "💊",
                    "document": "📚",
                    "emergency": "🚨",
                }
                route = meta.get("route", "")
                if route:
                    icon = route_icons.get(route, "🔀")
                    c2.caption(f"{icon} {route}")
                srcs = normalize_sources(meta.get("sources") or [])
                if srcs:
                    source_key = f"sources_{msg_idx}"
                    st.markdown(
                        f"""
                        <style>
                          div.st-key-{source_key} button {{
                            background: #f3f4f6 !important;
                            border: 1px solid #e5e7eb !important;
                            color: #374151 !important;
                            border-radius: 10px !important;
                            transition: all 0.15s ease !important;
                            min-height: 2.2rem !important;
                            min-width: 2.6rem !important;
                            padding: 0.25rem 0.45rem !important;
                            font-size: 1rem !important;
                          }}
                          div.st-key-{source_key} button:hover {{
                            background: #dbeafe !important;
                            border-color: #60a5fa !important;
                            color: #1d4ed8 !important;
                            transform: translateY(-1px);
                          }}
                          div.st-key-{source_key} button:active {{
                            background: #bfdbfe !important;
                            border-color: #3b82f6 !important;
                            color: #1d4ed8 !important;
                          }}
                        </style>
                        """,
                        unsafe_allow_html=True,
                    )
                    if c3.button("\U0001F4C3", key=source_key, use_container_width=False, help="Sources"):
                        open_source_modal(srcs)
                        st.rerun()

            # Suggested followups: hiện dưới tin nhắn assistant CUỐI CÙNG
            is_last_assistant = (
                msg["role"] == "assistant"
                and msg_idx == len(msgs) - 1
            )
            if is_last_assistant and len(msgs) >= 2:
                last_user_q = next(
                    (m["content"] for m in reversed(msgs) if m["role"] == "user"), ""
                )
                followups = get_followups(last_user_q)
                st.markdown("""
                <div class="followup-box">
                  <div class="followup-title">❓ Câu hỏi liên quan</div>
                </div>
                """, unsafe_allow_html=True)
                for fq in followups:
                    if st.button(
                        fq,
                        key=f"fq_{msg_idx}_{fq[:20]}",
                        use_container_width=True,
                    ):
                        st.session_state._example_query = fq
                        st.rerun()

    render_source_modal()

    # ── Chat input ──
    typed_prompt = st.chat_input("Nhập câu hỏi về tiểu đường, biến chứng, thuốc, chế độ ăn…")



    if hasattr(st.session_state, "_example_query"):
        prompt = st.session_state._example_query
        del st.session_state._example_query
    else:
        prompt = typed_prompt

    if prompt:
        safe_prompt = prompt.strip()
        remember_now = st.session_state.remember_knowledge
        teach_prefixes = (
            "/nho ",
            "nhớ rằng ",
            "ghi nhớ rằng ",
            "lưu ý rằng ",
            "thông tin của tôi là ",
            "tri thức mới: ",
        )
        lowered_prompt = safe_prompt.lower()
        for prefix in teach_prefixes:
            if lowered_prompt.startswith(prefix):
                remember_now = True
                break
        if len(safe_prompt) < 3:
            st.warning("Hãy nhập thêm nội dung sau `/nho` hoặc `nhớ rằng`.")
            st.stop()

        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        t0 = time.time()
        answer, meta_info = "", {}
        with st.chat_message("assistant", avatar="🏥"):
            with st.spinner("🤔 Đang phân tích tài liệu và soạn câu trả lời…"):
                try:
                    resp = requests.post(
                        f"{RAG_API_URL}/chat/session",
                        json={
                            "session_id": st.session_state.session_id,
                            "message": safe_prompt,
                            "top_k": 6,
                            "remember_knowledge": remember_now,
                        },
                        timeout=REQUEST_TIMEOUT,
                    )
                    resp.raise_for_status()
                    data   = resp.json()
                    answer = data.get("response", "Không có phản hồi")

                    meta_info = {
                        "ms":     data.get("response_time_ms",
                                           int((time.time() - t0) * 1000)),
                        "chunks": data.get("chunks_used", 0),
                        "sources": normalize_sources(data.get("sources", [])),
                        "route":  data.get("route_type", "document"),
                    }
                except requests.exceptions.ConnectionError:
                    answer = "❌ Không kết nối được API. Kiểm tra `docker-compose up`."
                except requests.exceptions.Timeout:
                    answer = "⏱ Quá thời gian chờ. Thử lại hoặc tăng timeout."
                except Exception as e:
                    answer = f"❌ Lỗi: {e}"

        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({"role": "assistant", "content": answer, "meta": meta_info})

        st.rerun()


# ═══════════════════════════════════════════════════════════
# TAB 2 — CRAWLER
# ═══════════════════════════════════════════════════════════
with tab_crawler:
    st.markdown("## 🕷 Crawl & Cập Nhật Dữ Liệu")
    st.caption("Quản lý quá trình thu thập tài liệu y tế và đồng bộ vào Qdrant")

    pdf_counts = count_pdfs_by_category()
    total_files = sum(pdf_counts.values())

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("### ⚙️ Đồng bộ Vector DB")
        st.write(f"Hiện có **{total_files}** file trong `data/pdfs/`.")
        st.caption(
            "Crawler chạy độc lập qua dòng lệnh (`scripts/crawler.py`, "
            "`scripts/crawl_vinmec.py`). Sau khi có file mới, dùng nút dưới "
            "để rebuild lại toàn bộ index Qdrant từ `data/pdfs/`."
        )

        if st.button("🔄 Rebuild Index Từ data/pdfs/", type="primary", use_container_width=True):
            with st.spinner("📥 Đang rebuild index — có thể mất vài phút…"):
                log = call_admin_rebuild()
                st.session_state.rebuild_log = log
            st.success("✅ Hoàn tất!")
            st.rerun()

        st.divider()
        st.markdown("**Chạy crawler thủ công trong terminal:**")
        st.code("docker exec rag-api python scripts/crawler.py --ingest", language="bash")
        st.code("docker exec rag-api python scripts/crawl_vinmec.py --max-articles 50 --ingest",
                language="bash")
        st.code("docker exec rag-api python scripts/ingest.py", language="bash")

    with col_right:
        st.markdown("### 📋 Phân bổ theo danh mục")
        if not pdf_counts:
            st.info("📭 Chưa có file nào trong data/pdfs/")
        else:
            for cat, count in sorted(pdf_counts.items(), key=lambda x: -x[1]):
                badge = '<span class="badge badge-ok">✅</span>' if count >= 3 else \
                        '<span class="badge badge-warn">⚠</span>' if count > 0 else \
                        '<span class="badge badge-none">⭕</span>'
                st.markdown(f"""
                <div class="cat-card">
                  <div>
                    <span class="cat-name">📂 {cat}</span><br>
                    <span class="cat-count">{count} file</span>
                  </div>
                  {badge}
                </div>""", unsafe_allow_html=True)

    if st.session_state.rebuild_log:
        st.divider()
        st.markdown("### 📜 Log")
        st.code(st.session_state.rebuild_log[-5000:], language="bash")
        if st.button("🗑 Xóa log"):
            st.session_state.rebuild_log = ""
            st.rerun()


# ═══════════════════════════════════════════════════════════
# TAB 3 — TÀI LIỆU
# ═══════════════════════════════════════════════════════════
with tab_docs:
    st.markdown("## 📚 Quản Lý Tài Liệu")

    pdf_counts  = count_pdfs_by_category()
    total_files = sum(pdf_counts.values())
    health      = get_api_health()
    chunks      = health.get("total_chunks", 0) if health else 0

    c1, c2, c3 = st.columns(3)
    c1.markdown(f'<div class="stat-box"><div class="stat-num">{total_files}</div>'
                f'<div class="stat-label">📄 Tổng tài liệu</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="stat-box"><div class="stat-num">{len(pdf_counts)}</div>'
                f'<div class="stat-label">📂 Danh mục có file</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="stat-box"><div class="stat-num">{chunks:,}</div>'
                f'<div class="stat-label">🧩 Chunks đã index</div></div>', unsafe_allow_html=True)

    with st.expander("🔧 Debug — đường dẫn thư mục", expanded=False):
        st.code(f"PDF_DIR = {PDF_DIR}\nExists = {PDF_DIR.exists()}", language="bash")

    st.divider()
    st.markdown("### 📁 Duyệt theo thư mục")

    if not pdf_counts:
        st.warning(f"📭 Chưa thấy file nào tại `{PDF_DIR}`")
        st.info("Kiểm tra volume mount trong docker-compose.yml:\n"
                "```yaml\nstreamlit:\n  volumes:\n    - ./data/pdfs:/app/data/pdfs\n```")
    else:
        from collections import defaultdict
        grouped = defaultdict(list)
        for fi in get_all_files_flat():
            grouped[fi["folder"]].append(fi)

        for folder, flist in sorted(grouped.items()):
            pdf_c = sum(1 for f in flist if f["ext"] == ".pdf")
            txt_c = sum(1 for f in flist if f["ext"] == ".txt")
            label = f"📂 {folder}  ({len(flist)} file: {pdf_c} PDF, {txt_c} TXT)"
            with st.expander(label, expanded=False):
                for fi in flist:
                    icon = "📕" if fi["ext"] == ".pdf" else "📄"
                    size = fi["size_kb"]
                    size_str = f"{size} KB" if size < 1024 else f"{size/1024:.1f} MB"
                    st.markdown(f"{icon} `{fi['name']}` — **{size_str}**")

    st.divider()
    st.markdown("### ➕ Upload tài liệu thủ công")

    up_c1, up_c2 = st.columns(2)
    with up_c1:
        uploaded_file = st.file_uploader("Chọn PDF hoặc TXT", type=["pdf", "txt"])
        doc_category  = st.selectbox("Danh mục", [
            "general", "diagnosis", "diet", "medication", "blood_glucose",
            "lifestyle", "emergency", "cardiovascular", "nephropathy",
            "neuropathy", "retinopathy", "foot_care", "pregnancy",
        ])
    with up_c2:
        doc_language = st.selectbox("Ngôn ngữ", ["vi", "en"])
        doc_title    = st.text_input("Tiêu đề (tùy chọn)")
        doc_verified = st.checkbox("Đã xác minh bởi bác sĩ", value=False)

    if uploaded_file and st.button("📤 Upload lên Qdrant", type="primary"):
        with st.spinner("Đang upload…"):
            try:
                resp = requests.post(
                    f"{RAG_API_URL}/admin/upload",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)},
                    data={"category": doc_category, "language": doc_language,
                          "title": doc_title or uploaded_file.name,
                          "source_name": uploaded_file.name,
                          "verified_by_doctor": str(doc_verified).lower()},
                    headers=admin_headers(),
                    timeout=120,
                )
                if resp.status_code == 200:
                    st.success(f"✅ {resp.json().get('chunks_indexed', 0)} chunks đã index!")
                elif resp.status_code == 422:
                    st.error(f"❌ PDF không đọc được text (có thể là file scan): {resp.text[:200]}")
                else:
                    st.error(f"❌ Lỗi {resp.status_code}: {resp.text[:300]}")
            except Exception as e:
                st.error(f"❌ {e}")


# ═══════════════════════════════════════════════════════════
# TAB 4 — THỐNG KÊ
# ═══════════════════════════════════════════════════════════
with tab_stats:
    st.markdown("## 📊 Thống Kê Vector Database")

    health = get_api_health()
    if not health:
        st.error("❌ Không kết nối được API.")
        st.code("docker-compose ps\ndocker-compose logs rag-api --tail=30", language="bash")
    else:
        try:
            sr = requests.get(f"{RAG_API_URL}/stats", timeout=10)
            stats = sr.json() if sr.status_code == 200 else {}
        except Exception:
            stats = {}

        total_chunks = stats.get("total_chunks", health.get("total_chunks", 0))
        categories   = stats.get("categories", {})
        emb_model    = stats.get("embedding_model", "N/A")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🧩 Tổng chunks", f"{total_chunks:,}")
        c2.metric("📂 Danh mục",    len(categories))
        c3.metric("📐 Chunk size",  stats.get("chunk_size", 900))
        c4.metric("🧠 Model", emb_model.split("/")[-1] if "/" in emb_model else emb_model)

        st.divider()
        if categories:
            st.markdown("### 📊 Phân bổ chunks theo danh mục")
            st.bar_chart(dict(sorted(categories.items(), key=lambda x: -x[1])), height=320)
        else:
            st.info("ℹ️ Chưa có dữ liệu. Hãy crawl/upload tài liệu rồi rebuild index.")

        st.divider()
        st.markdown("### 🔍 Thử vector search")
        q     = st.text_input("Nhập câu truy vấn:")
        top_k = st.slider("Top K", 1, 10, 4)
        if q and st.button("🔎 Tìm"):
            with st.spinner("Đang tìm…"):
                try:
                    r    = requests.get(f"{RAG_API_URL}/search", params={"q": q, "top_k": top_k}, timeout=30)
                    hits = r.json().get("results", [])
                    if not hits:
                        st.info("Không tìm thấy kết quả.")
                    for h in hits:
                        score = h.get("similarity", 0)
                        meta  = h.get("metadata", {})
                        with st.expander(
                            f"[{score:.3f}] 📄 {meta.get('document_title', meta.get('source',''))[:60]} "
                            f"— {meta.get('category','')} [{meta.get('language','?')}]"
                        ):
                            st.caption(f"Nguồn: {meta.get('source','N/A')} | Lang: {meta.get('language','?')}")
                            st.markdown(h.get("text", ""))
                except Exception as e:
                    st.error(f"❌ {e}")
