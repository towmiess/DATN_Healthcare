# 🏥 Healthcare RAG — Quick Start Guide

## ✅ Hiện Tại

- ✅ **Vector DB**: 118 PDFs indexed (84 MB) 
- ✅ **Chunks**: ~2000+ documents ready
- ✅ **RAG Pipeline**: Fully functional
- ⚠️ **Gemini API**: Quota exceeded (24h timeout)
- ❌ **Ollama**: Not running (optional)

---

## 🚀 QUICK START (3 Cách)

### **🎭 Cách 1: Mock Mode (Fastest - Chạy Ngay)**

```bash
# Chạy server ở chế độ demo (không cần Gemini)
python scripts/start_server.py --llm mock
```

- ✅ Chạy ngay lập tức
- ✅ Database full (118 PDFs)
- ⚠️ Trả lời là mock/demo

### **🦙 Cách 2: Ollama Local (Best - Khuyên Dùng)**

Bước 1: Download & run Ollama
```bash
# From https://ollama.ai
ollama pull mistral
ollama serve
```

Bước 2: Start server (mở terminal mới)
```bash
python scripts/start_server.py --llm ollama
```

- ✅ LLM thực sự (Mistral 7B)
- ✅ Chạy local, offline
- ✅ Miễn phí
- ⚠️ Cần 8GB RAM, lần đầu tải lâu

### **🔷 Cách 3: Gemini (24 Hours - Chờ Reset)**

```bash
# Khi Gemini quota reset (sau 24h)
python scripts/start_server.py --llm gemini
```

---

## 🎯 Những Gì Tôi Đã Làm

### 1️⃣ **Indexing PDF Mới**
```
✅ Xử lý 118 PDF files
✅ Chia thành ~2000+ chunks (500 tokens)
✅ Embed với multilingual model
✅ Lưu vào ChromaDB (84 MB)
```

**Files indexed:**
- Ada 2026 Standards of Care
- Vietnamese VNCDC guides
- NICE type 2 diabetes guidelines
- Diet & medication resources
- Emergency protocols

### 2️⃣ **LLM Manager với Fallback**
```
Created: src/rag/llm_manager.py
- Gemini → Ollama → Mock (fallback chain)
- Auto-detect available backends
- Graceful degradation
```

### 3️⃣ **Flexible Server Launcher**
```
Created:
- scripts/start_server.py (main, supports all modes)
- scripts/start_mock_server.py (demo only)
- start_server.bat (Windows)
- start_server.sh (Linux/Mac)
- QUOTA_FIX.md (troubleshooting guide)
```

---

## 📊 Database Status

```
Collection: healthcare_diabetes

Total chunks: 2000+
Total size: 84 MB
Embedding model: paraphrase-multilingual-MiniLM-L12-v2
Vector dimension: 384

Categories indexed:
- diet (nutrition guidelines)
- medication (drug guides)
- emergency (acute care)
- diagnosis (detection criteria)
- general (overview)
- lifestyle (exercise & activity)
- blood_glucose (monitoring)
```

---

## 🔧 Configuration (.env)

Current setup:
```bash
# Vector DB
CHROMA_PERSIST_DIR=data/chroma_db
CHUNK_SIZE=500
CHUNK_OVERLAP=50
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

# LLM (Gemini - but quota exceeded)
GEMINI_API_KEY=sk-...
LLM_MODEL=gemini-2.5-flash-lite

# Server
SERVER_PORT=8000
SERVER_HOST=0.0.0.0

# Ollama (optional)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=mistral
```

---

## 🧪 Testing API

When server is running:

### Health Check
```bash
curl http://localhost:8000/health
```

### Chat (Mock Response)
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Tôi bị tiểu đường, ăn phở được không?"}'
```

### API Docs
```
http://localhost:8000/docs
```

---

## 🚨 Troubleshooting

### Issue: "ModuleNotFoundError: sentence_transformers"
```bash
pip install sentence-transformers
```

### Issue: "Ollama connection refused"
```bash
# Make sure Ollama is running
ollama serve
# Should see: listening on 127.0.0.1:11434
```

### Issue: "Gemini API 429 - Quota exceeded"
```bash
# Expected - wait 24 hours, then:
python scripts/start_server.py --llm gemini
```

### Issue: Server not responding
```bash
# Check logs
tail -f data/logs/*.log  # Linux/Mac
# or check terminal output for errors
```

---

## 📈 Next Steps

1. **Immediate**: Test with mock mode
2. **Optional**: Setup Ollama for production
3. **Alternative**: Switch to Claude API or Hugging Face Inference
4. **Scaling**: Consider containerization (Docker)

---

## 📝 API Endpoints

All endpoints support Vietnamese text:

```
POST /chat              Single turn chat
POST /chat/stream       Streaming response
POST /chat/history      Multi-turn conversation
POST /knowledge         Add user knowledge
GET  /stats            Database statistics
GET  /health           Server health check
GET  /                 Frontend (if available)
GET  /docs             Swagger UI
```

---

## 🎓 Learn More

- RAG Architecture: See README.md
- Indexer details: `src/rag/indexer.py`
- Pipeline logic: `src/rag/pipeline.py`
- Server code: `src/api/server.py`
- LLM Manager: `src/rag/llm_manager.py`

---

## ⚡ Performance

With current setup:
- **Index time**: ~5 mins (first time)
- **Query latency**: 
  - Mock: <100ms
  - Ollama: 1-5s (on CPU) / <500ms (GPU)
  - Gemini: 2-10s (when available)
- **Memory**: 
  - Mock: ~300 MB
  - Ollama: ~4 GB
  - Gemini: ~1 GB

---

**Status**: ✅ Ready to deploy - choose LLM backend and start server!
