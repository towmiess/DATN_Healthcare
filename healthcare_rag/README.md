# 🏥 Healthcare RAG Chatbot — Hệ Thống Tư Vấn Y Tế Tiểu Đường

> RAG (Retrieval-Augmented Generation) + Gemini AI + ChromaDB

---

## 📐 Kiến Trúc Tổng Quan

```
Người dùng hỏi: "Tôi bị tiểu đường, ăn phở được không?"
        │
        ▼
┌─────────────────┐      ┌──────────────────────────────┐
│  FastAPI Server │─────►│  VectorIndexer (ChromaDB)    │
│  src/api/       │      │  - Embed câu hỏi             │
└────────┬────────┘      │  - Tìm top-5 chunks liên quan│
         │               └──────────────┬───────────────┘
         │                              │
         │         ┌────────────────────▼─────────────────────┐
         │         │  Context (tài liệu y khoa liên quan)      │
         │         │  "Phở có GI cao 65-70..."                 │
         │         │  "Người tiểu đường nên ăn tinh bột GI..."│
         │         └────────────────────┬─────────────────────┘
         │                              │
         ▼                              ▼
┌────────────────────────────────────────────────────┐
│  Gemini LLM  (gemini-2.5-flash)                    │
│  System: "Bạn là chuyên gia tư vấn tiểu đường..." │
│  Prompt: [Context từ DB] + [Câu hỏi user]          │
└────────────────────┬───────────────────────────────┘
                     │
                     ▼
       "Phở có chỉ số GI cao (65-70), làm đường
        huyết tăng nhanh. Bạn nên: 1) Đo đường
        huyết ngay, 2) Đi bộ nhẹ 15-20 phút..."
```

---

## 🗂 Cấu Trúc Thư Mục

```
healthcare_rag/
├── src/
│   ├── crawler/
│   │   └── medical_crawler.py    ← Bước 1: Thu thập tài liệu
│   ├── preprocessor/
│   │   └── pdf_builder.py        ← Bước 2: Chuẩn hóa PDF
│   ├── rag/
│   │   ├── indexer.py            ← Bước 3: Xây dựng Vector DB
│   │   └── pipeline.py           ← Bước 4: RAG Pipeline (core)
│   └── api/
│       └── server.py             ← Bước 5: FastAPI backend
├── frontend/
│   └── index.html                ← Giao diện chatbot
├── data/
│   ├── raw/                      ← Tài liệu crawl về (.txt)
│   ├── processed/                ← Text đã làm sạch
│   ├── pdfs/                     ← PDF chuẩn hóa
│   └── chroma_db/                ← Vector database
├── scripts/
│   └── run_pipeline.py           ← Chạy toàn bộ pipeline
├── requirements.txt
└── .env.example
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy

### Bước 0: Chuẩn bị môi trường

```bash
# Giải nén project
unzip healthcare_rag.zip
cd healthcare_rag

# Tạo virtual environment (khuyến nghị)
python -m venv venv

# Kích hoạt venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Cài thư viện
pip install -r requirements.txt
```

### Bước 1: Cấu hình API Key

```bash
# Copy file cấu hình mẫu
cp .env.example .env

# Mở .env và điền API key
# GEMINI_API_KEY=xxxxxxxxxx
# Lấy key tại: https://aistudio.google.com/app/apikey
```

### Bước 2: Chạy Pipeline (Tất cả trong 1 lệnh)

**Cách A — Demo nhanh (dùng dữ liệu mẫu, không cần internet):**
```bash
python scripts/run_pipeline.py --demo-only
```

**Cách B — Crawl thật từ internet:**
```bash
python scripts/run_pipeline.py
```

**Cách C — Chạy từng bước:**
```bash
# Bước 1: Crawl
python src/crawler/medical_crawler.py

# Bước 2: Build PDF
python src/preprocessor/pdf_builder.py

# Bước 3: Index
python src/rag/indexer.py

# Bước 4: Chạy server
uvicorn src.api.server:app --reload --port 8000
```

### Bước 3: Mở giao diện chatbot

1. Mở trình duyệt
2. Vào địa chỉ: `frontend/index.html` (kéo thả vào Chrome/Edge)
3. Hoặc test API trực tiếp: http://localhost:8000/docs

---

## 📡 API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/health` | Kiểm tra server |
| GET | `/stats` | Thống kê Vector DB |
| POST | `/chat` | Hỏi chatbot (single turn) |
| POST | `/chat/stream` | Hỏi chatbot (streaming) |
| POST | `/chat/history` | Hỏi với lịch sử (multi-turn) |
| GET | `/search?q=...` | Tìm kiếm trong Vector DB |

### Ví dụ gọi API:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Người tiểu đường ăn phở được không?", "top_k": 5}'
```

---

## 🔬 Giải Thích Kỹ Thuật

### Tại sao dùng RAG thay vì LLM thuần túy?

| | LLM thuần túy | RAG |
|--|--|--|
| Nguồn thông tin | Dữ liệu training (có thể lỗi thời) | Tài liệu y khoa cập nhật |
| Hallucination | Cao (bịa thông tin) | Thấp (có context cụ thể) |
| Trích dẫn nguồn | Không có | Có (từ file cụ thể) |
| Cập nhật | Cần train lại | Chỉ cần thêm PDF mới |

### Embedding Model

Dùng `paraphrase-multilingual-MiniLM-L12-v2`:
- Hỗ trợ 50+ ngôn ngữ, bao gồm tiếng Việt
- Nhẹ (~120MB), chạy được trên CPU
- Tốt cho semantic search đa ngôn ngữ

### ChromaDB

- Vector DB chạy local, không cần cloud
- Dùng HNSW index cho tìm kiếm nhanh O(log n)
- Cosine similarity để đo độ tương đồng

---

## 🔧 Mở Rộng Hệ Thống

### Thêm tài liệu y khoa mới:

```python
# Trong src/crawler/medical_crawler.py
MEDICAL_SOURCES.append(
    MedicalSource(
        name="ten_nguon_moi",
        url="https://example.com/bai-viet-y-khoa",
        category="tieu_duong_type2",
        selector=".content",
    )
)
```

Sau đó chạy lại:
```bash
python src/crawler/medical_crawler.py
python src/preprocessor/pdf_builder.py
python src/rag/indexer.py
```

### Thêm PDF sẵn có:

Chỉ cần copy file PDF vào `data/pdfs/` rồi chạy lại indexer:
```bash
cp your_medical_doc.pdf data/pdfs/
python src/rag/indexer.py
```

---

## ⚠️ Lưu Ý Quan Trọng

1. **Không thay thế bác sĩ**: Chatbot chỉ cung cấp thông tin tham khảo
2. **API Key bảo mật**: Không commit file `.env` lên Git
3. **Crawl lịch sự**: Script có delay 2s giữa các request để không làm quá tải server
4. **Tiếng Việt**: Embedding model hỗ trợ tốt tiếng Việt, nhưng tài liệu tiếng Anh cũng được index

---

## 📦 Tech Stack

- **LLM**: Gemini 2.5 Flash
- **Embedding**: sentence-transformers (multilingual)
- **Vector DB**: ChromaDB (local)
- **Backend**: FastAPI + Uvicorn
- **PDF**: reportlab + PyMuPDF + fpdf2
- **Crawler**: requests + BeautifulSoup4
- **Frontend**: HTML/CSS/JS thuần
