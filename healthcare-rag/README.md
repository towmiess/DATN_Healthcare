# Healthcare RAG v2 — Tiểu Đường AI Chatbot

Stack: **FastAPI + Qdrant + Redis + Gemini + Streamlit**

---

## 🚀 Chạy Local (Windows)

### Bước 1: Copy PDF từ project cũ

```powershell
# Mở PowerShell, cd vào thư mục project này
cd healthcare-rag-v2

# Copy toàn bộ PDF từ healthcare_rag cũ
xcopy ..\healthcare_rag\data\pdfs .\data\pdfs /E /I /Y
```

### Bước 2: Cấu hình .env

```powershell
# Mở file .env, điền API key
notepad .env
```

Sửa dòng:
```env
GEMINI_API_KEY_1=your_gemini_api_key_here
# Nếu có key 2, bỏ comment:
# GEMINI_API_KEY_2=AIza...key2...
```

### Bước 3: Khởi động Qdrant + Redis

```powershell
docker-compose up qdrant redis -d
```

Chờ ~10 giây, kiểm tra:
```powershell
# Qdrant phải trả về {"status": "ok"}
curl http://localhost:6333/health
```

### Bước 4: Tạo thư mục và Index PDF

```powershell
# Cài deps Python (lần đầu)
pip install -r requirements.txt

# Tạo cấu trúc thư mục
python scripts/init_folders.py

# Index tất cả PDF vào Qdrant (~5-10 phút tùy số lượng)
python scripts/ingest.py
```

Kiểm tra kết quả tại: **http://localhost:6333/dashboard**

### Bước 5: Khởi động toàn bộ

```powershell
docker-compose up -d
```

### Bước 6: Kiểm tra

| Service | URL |
|---------|-----|
| Chat UI | http://localhost:8501 |
| API Swagger | http://localhost:8000/docs |
| Qdrant Dashboard | http://localhost:6333/dashboard |
| Health check | http://localhost:8000/health |

---

## 📁 Cấu Trúc Thư Mục PDF

```
data/pdfs/
├── general/              # Kiến thức chung về tiểu đường
├── diagnosis/            # Chẩn đoán & phân loại
├── blood_glucose/        # Theo dõi đường huyết, HbA1c
├── medication/           # Thuốc điều trị
├── diet/                 # Chế độ ăn uống
├── lifestyle/            # Lối sống, vận động
├── emergency/            # Hạ/tăng đường huyết cấp cứu
└── complication/         # Biến chứng tiểu đường
    ├── cardiovascular/   # Tim mạch, đột quỵ
    ├── nephropathy/      # Bệnh thận
    ├── retinopathy/      # Bệnh võng mạc
    ├── neuropathy/       # Bệnh thần kinh
    └── foot_care/        # Chăm sóc bàn chân
```

**Đặt tên file:** `{category}__{tên_nguồn}.pdf`  
Ví dụ: `cardiovascular__aha_heart_guidelines_2024.pdf`

**Khi thêm PDF mới:**
```powershell
# Copy file vào đúng thư mục, rồi chạy:
python scripts/ingest.py --incremental
```

---

## 🔧 Lệnh Thường Dùng

```powershell
# Xem logs
docker-compose logs -f rag-api

# Restart API sau khi sửa code
docker-compose restart rag-api

# Dừng tất cả
docker-compose down

# Xóa hoàn toàn (kể cả data Qdrant/Redis)
docker-compose down -v

# Index lại từ đầu
python scripts/ingest.py

# Index chỉ file mới
python scripts/ingest.py --incremental
```

---

## 🌐 Deploy AWS (Phase 2)

Sau khi local ổn định:

1. Build và push image lên ECR
2. Thay Qdrant local → Qdrant Cloud hoặc EC2
3. Thay Redis local → ElastiCache
4. Deploy rag-api + streamlit lên ECS Fargate
5. Dùng ALB làm load balancer

Chi tiết hướng dẫn AWS sẽ bổ sung sau khi local hoàn chỉnh.

---

## 📊 API Endpoints

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/health` | Kiểm tra server |
| GET | `/stats` | Thống kê DB |
| POST | `/chat` | Hỏi đáp đơn |
| POST | `/chat/session` | Multi-turn (lưu session Redis) |
| POST | `/chat/stream` | Streaming response |
| DELETE | `/chat/session/{id}` | Xóa lịch sử session |
| GET | `/search?q=...` | Debug vector search |
| POST | `/admin/upload` | Upload PDF/TXT mới |
| GET | `/admin/documents` | Danh sách tài liệu |
| DELETE | `/admin/documents/{id}` | Xóa tài liệu |
| POST | `/admin/rebuild-index` | Index lại toàn bộ |

**Admin endpoints** cần header: `X-Admin-Token: healthcare-admin-dev`
