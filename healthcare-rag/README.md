# Healthcare RAG v2 — Refactored

Chatbot tư vấn tiểu đường: **FastAPI + Qdrant + Redis + Gemini + Streamlit**

---

## Kiến Trúc Module

```
src/
├── ingestion/
│   ├── loader.py       ← Load PDF/TXT, detect category + language
│   └── ocr.py          ← OCR fallback (Tesseract) cho PDF scan
├── chunking/
│   └── chunker.py      ← Chia tài liệu thành chunks (LangChain)
├── embeddings/
│   └── embedder.py     ← Singleton SentenceTransformer
├── vectordb/
│   └── vector_store.py ← Qdrant upsert / search / stats
├── retrieval/
│   └── retriever.py    ← Intent detection + semantic reranking
├── prompts/
│   └── templates.py    ← System prompt + RAG prompt builder
├── llm/
│   └── gemini_client.py← Key pool rotation + retry + fallback
├── rag/
│   ├── pipeline.py     ← Orchestrate Retrieve→Generate + Cache
│   └── session.py      ← Redis session (fallback in-memory)
└── api/
    └── server.py       ← FastAPI endpoints
```

---

## Chạy Local (Windows)

```powershell
# 1. Copy file .env
copy .env.example .env
notepad .env   # điền GEMINI_API_KEY_1

# 2. Khởi động Qdrant + Redis
docker-compose up qdrant redis -d

# 3. Tạo thư mục và copy PDF
python scripts/init_folders.py
xcopy ..\healthcare_rag\data\pdfs .\data\pdfs /E /I /Y

# 4. Cài deps Python
pip install torch==2.1.2+cpu --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 5. Index PDF vào Qdrant (~5-15 phút)
python scripts/ingest.py

# 6. Khởi động tất cả
docker-compose up -d
```

| Service | URL |
|---------|-----|
| Chat UI | http://localhost:8501 |
| API Docs | http://localhost:8000/docs |
| Qdrant | http://localhost:6333/dashboard |

---

## Chạy Tests (Không Cần Qdrant/GPU)

```bash
# Tất cả tests
python -m pytest tests/ -v

# Từng test
python tests/test_intent.py
python tests/test_chunker.py
python tests/test_loader.py
python tests/test_ocr.py
```

---

## Lệnh Thường Dùng

```powershell
# Index tất cả PDF
python scripts/ingest.py

# Chỉ index file mới
python scripts/ingest.py --incremental

# Crawl thêm dữ liệu
docker exec rag-api python scripts/crawler.py --ingest

# Xem logs
docker-compose logs -f rag-api

# Restart API sau sửa code
docker-compose restart rag-api

# Xóa hoàn toàn (kể cả data Qdrant)
docker-compose down -v
```

---

## API Endpoints

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/health` | Kiểm tra server |
| GET | `/stats` | Thống kê chunks |
| POST | `/chat` | Single-turn |
| POST | `/chat/session` | Multi-turn (Redis) |
| POST | `/chat/stream` | Streaming SSE |
| DELETE | `/chat/session/{id}` | Xóa session |
| GET | `/search?q=...` | Debug search |
| POST | `/admin/upload` | Upload PDF/TXT |
| GET | `/admin/documents` | Danh sách tài liệu |
| DELETE | `/admin/documents/{id}` | Xóa tài liệu |
| POST | `/admin/rebuild-index` | Index lại tất cả |

Admin: header `X-Admin-Token: healthcare-admin-dev`
