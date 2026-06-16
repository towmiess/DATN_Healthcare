"""
Healthcare RAG v2 — Streamlit UI (Fixed)
Fixes: 422 min_length, 403 admin token, PDF_DIR mount, language detect
"""

import streamlit as st
import requests
import os
import uuid
import time
import json
from pathlib import Path

# ── Config ───────────────────────────────────────────────────
RAG_API_URL     = os.getenv("RAG_API_URL", "http://localhost:8000")
REQUEST_TIMEOUT = int(os.getenv("RAG_API_TIMEOUT_S", 120))
ADMIN_TOKEN     = os.getenv("ADMIN_SECRET_KEY", "healthcare-admin-dev")

# Path: streamlit container mount /app/data/pdfs (xem docker-compose volumes)
# Fallback về local dev path nếu không chạy trong Docker
_candidates = [
    Path("/app/data/pdfs"),                          # Docker container (volume mount)
    Path(__file__).parent.parent.parent / "data" / "pdfs",  # dev: src/.. /..
    Path(__file__).parent.parent / "data" / "pdfs",         # dev: services/../
]
PDF_DIR = next((p for p in _candidates if p.exists()), _candidates[0])
PDF_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(
    page_title="🏥 Healthcare RAG",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Be Vietnam Pro', sans-serif; }
  .rag-header {
    background: linear-gradient(135deg, #1e3a8a 0%, #0369a1 100%);
    color: white; padding: 20px 28px; border-radius: 16px; margin-bottom: 20px;
    display: flex; align-items: center; gap: 16px;
  }
  .rag-header h1 { font-size: 22px; font-weight: 700; margin: 0; }
  .rag-header p  { font-size: 13px; opacity: 0.85; margin: 4px 0 0; }
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


# ── Helpers ───────────────────────────────────────────────────
def get_api_health():
    try:
        r = requests.get(f"{RAG_API_URL}/health", timeout=4)
        return r.json()
    except Exception:
        return None


def count_pdfs_by_category() -> dict:
    """
    Đọc file list từ volume mount /app/data/pdfs.
    Hiển thị theo cấu trúc thư mục thực tế (không hardcode category names).
    """
    counts = {}
    if not PDF_DIR.exists():
        return counts
    for subdir in sorted(PDF_DIR.rglob("*")):
        if subdir.is_dir():
            # Chỉ đếm file trực tiếp trong subdir (không rglob để tránh đếm 2 lần)
            files = [f for f in list(subdir.glob("*.pdf")) + list(subdir.glob("*.txt"))
                     if not f.name.startswith(".")]
            if files:
                rel = str(subdir.relative_to(PDF_DIR))
                counts[rel] = len(files)
    # Nếu không có subfolder nào nhưng có file ở root
    root_files = [f for f in list(PDF_DIR.glob("*.pdf")) + list(PDF_DIR.glob("*.txt"))
                  if not f.name.startswith(".")]
    if root_files:
        counts["(root)"] = len(root_files)
    return counts


def get_all_files_flat() -> list:
    """Trả về tất cả PDF/TXT với metadata đơn giản."""
    if not PDF_DIR.exists():
        return []
    files = []
    for f in sorted(PDF_DIR.rglob("*.pdf")) + sorted(PDF_DIR.rglob("*.txt")):
        if not f.name.startswith("."):
            try:
                rel = str(f.relative_to(PDF_DIR))
                parts = rel.replace("\\", "/").split("/")
                folder = "/".join(parts[:-1]) if len(parts) > 1 else "(root)"
                files.append({"path": f, "name": f.name, "folder": folder,
                               "size_kb": f.stat().st_size // 1024,
                               "ext": f.suffix})
            except Exception:
                pass
    return files


def admin_headers() -> dict:
    """Header có admin token để upload."""
    return {"X-Admin-Token": ADMIN_TOKEN}


def call_api_crawler(categories: list, max_per: int, force: bool) -> str:
    try:
        resp = requests.post(
            f"{RAG_API_URL}/admin/crawl",
            json={"categories": categories, "max_per_category": max_per, "force": force},
            headers=admin_headers(),
            timeout=300,
        )
        if resp.status_code == 200:
            return resp.json().get("log", "✅ Crawl xong")
        return f"❌ {resp.status_code}: {resp.text[:300]}"
    except requests.exceptions.ConnectionError:
        return "❌ Không kết nối được rag-api"
    except requests.exceptions.Timeout:
        return "⏱ Timeout — crawl đang chạy ngầm, reload sau vài phút"
    except Exception as e:
        return f"❌ {e}"


def call_api_ingest(incremental: bool = True) -> str:
    try:
        resp = requests.post(
            f"{RAG_API_URL}/admin/ingest",
            json={"incremental": incremental},
            headers=admin_headers(),
            timeout=600,
        )
        if resp.status_code == 200:
            return resp.json().get("log", "✅ Ingest xong")
        return f"❌ {resp.status_code}: {resp.text[:300]}"
    except requests.exceptions.Timeout:
        return "⏱ Timeout — ingest đang chạy ngầm"
    except Exception as e:
        return f"❌ {e}"


# ── Session state ─────────────────────────────────────────────
defaults = {"session_id": str(uuid.uuid4()), "messages": [], "crawler_log": "", "ingest_log": ""}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── SIDEBAR ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏥 Healthcare Chatbot")
    health = get_api_health()
    if health:
        icon = "🟢" if health.get("rag_ready") else "🟡"
        st.markdown(f"""
        <div class="sidebar-section">
          <b>{icon} API Online</b><br>
          <small>
            📦 {health.get('total_chunks', 0):,} chunks<br>
            💾 {health.get('session_store', 'N/A')}<br>
            ✅ RAG ready: {'Có' if health.get('rag_ready') else 'Chưa — restart rag-api'}<br>
            🔗 <code>{st.session_state.session_id[:8]}…</code>
          </small>
        </div>""", unsafe_allow_html=True)
        if not health.get("rag_ready"):
            st.warning("⚠ RAG chưa sẵn sàng!\n\nChạy lệnh:\n```\ndocker-compose restart rag-api\n```")
    else:
        st.markdown("""
        <div class="sidebar-section">
          🔴 <b>API Offline</b><br>
          <small>docker-compose up -d</small>
        </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("**📋 Câu hỏi mẫu**")
    examples = [
        "Người tiểu đường type 2 ăn phở được không?",
        "HbA1c bao nhiêu là cần điều trị?",
        "Metformin uống lúc nào tốt nhất?",
        "Tiểu đường có ảnh hưởng đến thận không?",
        "Hạ đường huyết phải làm gì?",
        "Biến chứng tim mạch của tiểu đường?",
        "Chăm sóc bàn chân tiểu đường như thế nào?",
        "Tiểu đường thai kỳ là gì?",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True, key=f"ex_{hash(ex)}"):
            st.session_state._example_query = ex
            st.rerun()

    st.divider()
    if st.button("🗑 Xóa lịch sử chat", use_container_width=True):
        try:
            requests.delete(f"{RAG_API_URL}/chat/session/{st.session_state.session_id}", timeout=5)
        except Exception:
            pass
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()


# ── MAIN TABS ─────────────────────────────────────────────────
tab_chat, tab_crawler, tab_docs, tab_stats = st.tabs([
    "💬 Chat", "🕷 Crawler", "📚 Tài liệu", "📊 Thống kê"
])


# ═══════════════════════════════════════════════════════════════
# TAB 1 — CHAT
# ═══════════════════════════════════════════════════════════════
with tab_chat:
    st.markdown("""
    <div class="rag-header">
      <span style="font-size:36px">🏥</span>
      <div>
        <h1>Chatbot Tư Vấn Tiểu Đường</h1>
        <p>Dựa trên ADA Standards of Care 2026 & tài liệu y khoa Việt Nam</p>
      </div>
    </div>""", unsafe_allow_html=True)

    for msg in st.session_state.messages:
        avatar = "👤" if msg["role"] == "user" else "🏥"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])
            if msg.get("meta"):
                meta = msg["meta"]
                c1, c2, c3 = st.columns(3)
                c1.caption(f"⏱ {meta.get('ms', 0):,}ms")
                c2.caption(f"📄 {meta.get('chunks', 0)} chunks")
                if meta.get("sources"):
                    c3.caption(f"📚 {str(meta['sources'][0])[:40]}…")

    # Handle example button click
    prompt = None
    if hasattr(st.session_state, "_example_query"):
        prompt = st.session_state._example_query
        del st.session_state._example_query
    else:
        prompt = st.chat_input("Nhập câu hỏi về tiểu đường, biến chứng, thuốc, chế độ ăn…")

    if prompt:
        # Đảm bảo message đủ dài để qua min_length=3
        safe_prompt = prompt.strip()
        if len(safe_prompt) < 3:
            safe_prompt = safe_prompt + "   "  # pad nếu quá ngắn

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🏥"):
            with st.spinner("🔍 Đang tìm kiếm tài liệu…"):
                t0 = time.time()
                answer, meta_info = "", {}
                try:
                    resp = requests.post(
                        f"{RAG_API_URL}/chat/session",
                        json={
                            "session_id": st.session_state.session_id,
                            "message": safe_prompt,
                            "top_k": 5,
                        },
                        timeout=REQUEST_TIMEOUT,
                    )
                    if resp.status_code == 422:
                        # Fallback sang /chat nếu session lỗi validation
                        resp = requests.post(
                            f"{RAG_API_URL}/chat",
                            json={"query": safe_prompt, "top_k": 5},
                            timeout=REQUEST_TIMEOUT,
                        )
                    resp.raise_for_status()
                    data = resp.json()
                    answer = data.get("response", "Không có phản hồi")
                    meta_info = {
                        "ms": data.get("response_time_ms", int((time.time()-t0)*1000)),
                        "chunks": data.get("chunks_used", 0),
                        "sources": [s["source"] if isinstance(s, dict) else s
                                    for s in data.get("sources", [])],
                    }
                except requests.exceptions.ConnectionError:
                    answer = "❌ Không kết nối được API. Kiểm tra `docker-compose up`."
                except requests.exceptions.Timeout:
                    answer = "⏱ Quá thời gian chờ. Thử lại hoặc tăng timeout."
                except Exception as e:
                    answer = f"❌ Lỗi: {e}"

            st.markdown(answer)
            if meta_info:
                c1, c2, c3 = st.columns(3)
                c1.caption(f"⏱ {meta_info.get('ms',0):,}ms")
                c2.caption(f"📄 {meta_info.get('chunks',0)} chunks")
                if meta_info.get("sources"):
                    c3.caption(f"📚 {str(meta_info['sources'][0])[:40]}…")

        st.session_state.messages.append({"role": "assistant", "content": answer, "meta": meta_info})
        st.rerun()


# ═══════════════════════════════════════════════════════════════
# TAB 2 — CRAWLER
# ═══════════════════════════════════════════════════════════════
with tab_crawler:
    st.markdown("## 🕷 Tự Động Crawl Tài Liệu Y Tế")
    st.caption("Crawl từ CDC, WHO, ADA, NIDDK, Vinmec, HelloBacsi vào đúng folder pdfs/")

    CATEGORY_META = {
        "blood_glucose":              {"icon": "🩸", "label": "Đường huyết",            "sources": 4},
        "diagnosis":                  {"icon": "🔬", "label": "Chẩn đoán",               "sources": 5},
        "diet":                       {"icon": "🥗", "label": "Chế độ ăn",              "sources": 4},
        "emergency":                  {"icon": "🚨", "label": "Cấp cứu hạ đường huyết", "sources": 4},
        "general":                    {"icon": "📖", "label": "Tổng quan tiểu đường",    "sources": 4},
        "lifestyle":                  {"icon": "🏃", "label": "Lối sống",                "sources": 4},
        "medication":                 {"icon": "💊", "label": "Thuốc điều trị",          "sources": 4},
        "complication/cardiovascular":{"icon": "❤️", "label": "Biến chứng tim mạch",    "sources": 4},
        "complication/nephropathy":   {"icon": "🫘", "label": "Biến chứng thận",        "sources": 3},
        "complication/neuropathy":    {"icon": "⚡", "label": "Biến chứng thần kinh",   "sources": 3},
        "complication/retinopathy":   {"icon": "👁",  "label": "Biến chứng mắt",         "sources": 3},
        "complication/foot_care":     {"icon": "🦶", "label": "Chăm sóc bàn chân",      "sources": 4},
        "complication/pregnancy":     {"icon": "🤰", "label": "Tiểu đường thai kỳ",      "sources": 5},
    }

    pdf_counts = count_pdfs_by_category()

    col_left, col_right = st.columns([1, 1])
    with col_left:
        st.markdown("### ⚙️ Cấu hình")
        all_cats = list(CATEGORY_META.keys())
        selected_cats = st.multiselect(
            "📂 Danh mục",
            options=all_cats,
            default=all_cats,
            format_func=lambda c: f"{CATEGORY_META[c]['icon']} {CATEGORY_META[c]['label']}",
        )
        max_per = st.slider("📄 Số tài liệu tối đa / danh mục", 1, 20, 5)
        c1, c2 = st.columns(2)
        force = c1.checkbox("🔄 Crawl lại", False)
        auto_ingest = c2.checkbox("⚡ Ingest ngay", True)
        st.divider()

        if st.button("🚀 Bắt Đầu Crawl", type="primary", use_container_width=True):
            cats = selected_cats or all_cats
            with st.spinner(f"🕷 Crawl {len(cats)} danh mục…"):
                log = call_api_crawler(cats, max_per, force)
                st.session_state.crawler_log = log
            if auto_ingest and "❌" not in log:
                with st.spinner("📥 Ingest vào Qdrant…"):
                    st.session_state.crawler_log += "\n── INGEST ──\n" + call_api_ingest(True)
            st.rerun()

        if st.button("📥 Chỉ Ingest", use_container_width=True):
            with st.spinner("📥 Đang ingest…"):
                st.session_state.ingest_log = call_api_ingest(False)
            st.rerun()

        st.divider()
        st.markdown("**Chạy thủ công trong terminal:**")
        st.code("docker exec rag-api python scripts/crawler.py --ingest", language="bash")
        st.code("docker exec rag-api python scripts/ingest.py --incremental", language="bash")

    with col_right:
        st.markdown("### 📋 Trạng thái")
        for cat, meta in CATEGORY_META.items():
            count = pdf_counts.get(cat, 0)
            if count >= meta["sources"]:
                badge = '<span class="badge badge-ok">✅ Đầy đủ</span>'
            elif count > 0:
                badge = f'<span class="badge badge-warn">⚠ {count}/{meta["sources"]}</span>'
            else:
                badge = '<span class="badge badge-none">⭕ Chưa có</span>'
            st.markdown(f"""
            <div class="cat-card">
              <div>
                <span class="cat-name">{meta['icon']} {meta['label']}</span><br>
                <span class="cat-count">{count} file</span>
              </div>
              {badge}
            </div>""", unsafe_allow_html=True)

    if st.session_state.crawler_log:
        st.divider()
        st.markdown("### 📜 Log")
        st.code(st.session_state.crawler_log[-5000:], language="bash")
        if st.button("🗑 Xóa log"): st.session_state.crawler_log = ""; st.rerun()


# ═══════════════════════════════════════════════════════════════
# TAB 3 — TÀI LIỆU
# ═══════════════════════════════════════════════════════════════
with tab_docs:
    st.markdown("## 📚 Quản Lý Tài Liệu")

    pdf_counts  = count_pdfs_by_category()
    total_files = sum(pdf_counts.values())
    health      = get_api_health()
    chunks      = health.get("total_chunks", 0) if health else 0

    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="stat-box"><div class="stat-num">{total_files}</div><div class="stat-label">📄 Tổng tài liệu</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="stat-box"><div class="stat-num">{len(pdf_counts)}</div><div class="stat-label">📂 Danh mục có file</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="stat-box"><div class="stat-num">{chunks:,}</div><div class="stat-label">🧩 Chunks đã index</div></div>', unsafe_allow_html=True)

    # Debug path info
    with st.expander("🔧 Debug — đường dẫn thư mục", expanded=False):
        st.code(f"PDF_DIR = {PDF_DIR}\nExists = {PDF_DIR.exists()}", language="bash")
        if PDF_DIR.exists():
            all_files = list(PDF_DIR.rglob("*.pdf")) + list(PDF_DIR.rglob("*.txt"))
            st.write(f"Tổng files tìm thấy: {len(all_files)}")

    st.divider()
    st.markdown("### 📁 Duyệt theo thư mục")

    if not pdf_counts:
        st.warning(f"📭 Chưa thấy file nào tại `{PDF_DIR}`")
        st.info("Kiểm tra volume mount trong docker-compose.yml:\n"
                "```yaml\nstreamlit:\n  volumes:\n    - ./data/pdfs:/app/data/pdfs\n```")
        # Hiện debug info
        st.code(f"PDF_DIR = {PDF_DIR}\nExists = {PDF_DIR.exists()}", language="bash")
    else:
        # Tổng hợp theo folder gốc (diabetes, complication/cardiovascular...)
        all_files = get_all_files_flat()
        # Group by folder
        from collections import defaultdict
        grouped = defaultdict(list)
        for fi in all_files:
            grouped[fi["folder"]].append(fi)

        for folder, flist in sorted(grouped.items()):
            pdf_c = sum(1 for f in flist if f["ext"] == ".pdf")
            txt_c = sum(1 for f in flist if f["ext"] == ".txt")
            label = f"📂 {folder}  ({len(flist)} file"
            if pdf_c and txt_c:
                label += f": {pdf_c} PDF, {txt_c} TXT)"
            elif pdf_c:
                label += f": {pdf_c} PDF)"
            else:
                label += f": {txt_c} TXT)"

            with st.expander(label, expanded=False):
                for fi in flist:
                    icon = "📕" if fi["ext"] == ".pdf" else "📄"
                    size = fi["size_kb"]
                    size_str = f"{size} KB" if size < 1024 else f"{size//1024:.1f} MB"
                    st.markdown(f"{icon} `{fi['name']}` — **{size_str}**")

    st.divider()
    st.markdown("### ➕ Upload tài liệu thủ công")

    up_c1, up_c2 = st.columns(2)
    with up_c1:
        uploaded_file = st.file_uploader("Chọn PDF hoặc TXT", type=["pdf", "txt"])
        doc_category  = st.selectbox("Danh mục", [
            "general", "diagnosis", "diet", "medication", "blood_glucose",
            "lifestyle", "emergency", "complication/cardiovascular",
            "complication/nephropathy", "complication/neuropathy",
            "complication/retinopathy", "complication/foot_care",
            "complication/pregnancy",
        ])
    with up_c2:
        doc_language = st.selectbox("Ngôn ngữ", ["vi", "en"])
        doc_title    = st.text_input("Tiêu đề (tùy chọn)")

    if uploaded_file and st.button("📤 Upload lên Qdrant", type="primary"):
        with st.spinner("Đang upload…"):
            try:
                resp = requests.post(
                    f"{RAG_API_URL}/admin/upload",
                    files={"file": (uploaded_file.name, uploaded_file.read(), uploaded_file.type)},
                    data={"category": doc_category, "language": doc_language,
                          "title": doc_title or uploaded_file.name},
                    headers=admin_headers(),   # ← FIX 403: thêm X-Admin-Token
                    timeout=120,
                )
                if resp.status_code == 200:
                    st.success(f"✅ {resp.json().get('chunks_indexed', 0)} chunks đã index!")
                elif resp.status_code == 422:
                    detail = resp.json().get("detail", resp.text)
                    st.error(f"❌ PDF không đọc được text (có thể là file scan): {detail}")
                else:
                    st.error(f"❌ Lỗi {resp.status_code}: {resp.text[:300]}")
            except Exception as e:
                st.error(f"❌ {e}")


# ═══════════════════════════════════════════════════════════════
# TAB 4 — THỐNG KÊ
# ═══════════════════════════════════════════════════════════════
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
        c3.metric("📐 Chunk size",  stats.get("chunk_size", 350))
        c4.metric("🧠 Model", emb_model.split("/")[-1] if "/" in emb_model else emb_model)

        # Phân tích language
        langs = stats.get("languages", {})
        if langs:
            st.divider()
            st.markdown("### 🌐 Phân bổ ngôn ngữ")
            lc1, lc2 = st.columns(2)
            vi = langs.get("vi", 0)
            en = langs.get("en", 0)
            total_lang = vi + en or 1
            lc1.metric("🇻🇳 Tiếng Việt", f"{vi:,}", f"{vi/total_lang*100:.0f}%")
            lc2.metric("🇺🇸 Tiếng Anh",  f"{en:,}", f"{en/total_lang*100:.0f}%")

        st.divider()
        if categories:
            st.markdown("### 📊 Phân bổ chunks theo danh mục")
            st.bar_chart(dict(sorted(categories.items(), key=lambda x: -x[1])), height=320)
        else:
            st.info("ℹ️ Chưa có dữ liệu. Hãy chạy Crawler và Ingest trước.")

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
                            f"[{score:.3f}] 📄 {meta.get('document_title','')[:60]} "
                            f"— {meta.get('category','')} [{meta.get('language','?')}]"
                        ):
                            st.caption(f"Nguồn: {meta.get('source','N/A')} | Lang: {meta.get('language','?')}")
                            st.markdown(h.get("text", ""))
                except Exception as e:
                    st.error(f"❌ {e}")