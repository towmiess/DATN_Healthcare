# 🔧 GIẢI PHÁP GEMINI API QUOTA EXCEEDED

## 🚨 Vấn đề Hiện Tại
```
❌ Gemini API error 429: You exceeded your current quota
   Quota exceeded for metric: generativelanguage.googleapis.com/...
   Please retry in 24.372617675s.
```

Gemini free tier đã vượt quá hạn ngạch. Cần **24h** để reset.

---

## ✅ Giải Pháp Ngay Lập Tức (3 Cách)

### **CÁCH 1: Dùng Mock Mode (Nhanh Nhất - Không Cần Setup)**

```bash
cd d:\study\DATN\healthcare_rag
python scripts/start_mock_server.py
```

**Ưu điểm:**
- ✅ Chạy ngay, không cần cài gì
- ✅ Có database đầy đủ
- ✅ Trả lời demo cho các câu hỏi phổ biến

**Nhược điểm:**
- ❌ Trả lời là mock, không AI thực

---

### **CÁCH 2: Cài Ollama (Khuyên Dùng - Tốt Nhất)**

**Bước 1: Tải Ollama**
- Truy cập: https://ollama.ai/download
- Tải phiên bản Windows
- Cài đặt bình thường

**Bước 2: Chạy Ollama**

Mở PowerShell mới, chạy:
```bash
ollama pull mistral
ollama serve
```

(Lần đầu sẽ tải ~4GB model, chờ 5-10 phút)

**Bước 3: Chạy Server**

Mở PowerShell khác:
```bash
cd d:\study\DATN\healthcare_rag
python scripts/start_server.py --use-ollama
```

**Ưu điểm:**
- ✅ LLM thực (Mistral 7B, chạy local)
- ✅ Không cần API key
- ✅ Miễn phí, tốc độ nhanh
- ✅ Hoạt động offline

**Nhược điểm:**
- ❌ Cần 8GB RAM (hoặc GPU)
- ❌ Lần đầu tải lâu (~30 phút)

---

### **CÁCH 3: Chờ Gemini Reset (Miễn Phí Nhất)**

- ⏳ Chờ **24 giờ** để Gemini reset quota
- Thời gian còn lại: ~**24.37 giây** = 00:00:24 UTC

Khi reset, tự động dùng Gemini lại.

---

## 📋 CURRENT STATUS

```
✅ Vector DB: 84 MB (118 PDFs indexed)
✅ Chunks: ~2000+ documents
✅ RAG Pipeline: Ready
❌ Gemini API: QUOTA EXCEEDED (retry in 24h)
⏳ Ollama: NOT RUNNING (optional fallback)
🟡 Server: Ready to start with mock/ollama mode
```

---

## 🎯 Khuyến Cáo

**Tôi đã:**
1. ✅ Index tất cả PDF mới vào ChromaDB
2. ✅ Tạo LLM Manager với fallback strategy
3. ✅ Tạo mock server cho demo

**Bạn nên:**
1. **Ngay lập tức**: Dùng CÁCH 1 (mock mode) để test database
2. **Tốt nhất**: Setup CÁCH 2 (Ollama) để có LLM chất lượng cao
3. **Lâu dài**: Sử dụng Anthropic Claude API (free tier 500K tokens/month) hoặc Hugging Face Inference API

---

## 🔄 Chuyển Sang Model Khác (Tuỳ Chọn)

Nếu muốn dùng Claude thay vì Gemini:

```bash
# 1. Lấy API key từ https://console.anthropic.com
# 2. Thêm vào .env:
export ANTHROPIC_API_KEY="sk-ant-..."

# 3. Chạy server
python scripts/start_server.py --use-claude
```

---

## 📞 Support

- **Ollama issues?** → Xem https://github.com/ollama/ollama/issues
- **Gemini status?** → Kiểm tra https://ai.dev/rate-limit
- **Code issues?** → Check `src/rag/llm_manager.py`
