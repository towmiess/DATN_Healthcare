# 📋 Tài Liệu Yêu Cầu & Quy Trình Triển Khai
# Module RAG — Chatbot Tư Vấn Y Tế Tiểu Đường

> **Phiên bản:** 1.0  
> **Hệ thống:** Healthcare RAG Chatbot (Module con trong hệ thống chung)  
> **Tech stack:** Gemini 2.5 Flash · ChromaDB · FastAPI · sentence-transformers  

---

## Mục Lục

1. [Tổng Quan Module](#1-tổng-quan-module)
2. [Yêu Cầu Chức Năng](#2-yêu-cầu-chức-năng)
3. [Kiến Trúc Metadata-Aware Retrieval](#3-kiến-trúc-metadata-aware-retrieval)
4. [Quy Trình Thu Thập & Quản Lý Tài Liệu](#4-quy-trình-thu-thập--quản-lý-tài-liệu)
5. [Tính Năng Bổ Sung Tri Thức Từ Bác Sĩ](#5-tính-năng-bổ-sung-tri-thức-từ-bác-sĩ)
6. [Tích Hợp Dữ Liệu Bệnh Nhân](#6-tích-hợp-dữ-liệu-bệnh-nhân)
7. [Quy Trình Triển Khai Từng Bước](#7-quy-trình-triển-khai-từng-bước)
8. [Cấu Trúc Dữ Liệu & Schema](#8-cấu-trúc-dữ-liệu--schema)
9. [API Contract](#9-api-contract)
10. [Tiêu Chí Chấp Nhận & Kiểm Thử](#10-tiêu-chí-chấp-nhận--kiểm-thử)
11. [Checklist Training & Onboarding](#11-checklist-training--onboarding)

---

## 1. Tổng Quan Module

### 1.1 Vị Trí Trong Hệ Thống Chung

```
┌─────────────────────────────────────────────────────────────────┐
│                     HỆ THỐNG CHUNG                              │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │ Module Auth  │    │ Module Bệnh  │    │ Module Lịch Hẹn   │  │
│  │ & Hồ Sơ BN  │    │ Án Điện Tử  │    │ & Theo Dõi        │  │
│  └──────┬───────┘    └──────┬───────┘    └─────────┬─────────┘  │
│         │                   │                       │            │
│         └───────────────────┴───────────────────────┘            │
│                             │  Patient Context API               │
│                             ▼                                    │
│         ┌───────────────────────────────────────┐               │
│         │        MODULE RAG CHATBOT  ◄── bạn đang ở đây        │
│         │                                        │               │
│         │  • Metadata-Aware Retrieval            │               │
│         │  • Knowledge Base (ChromaDB)           │               │
│         │  • Doctor Knowledge Ingestion          │               │
│         │  • Patient-Personalized Response       │               │
│         └───────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Luồng Hoạt Động Tổng Thể

```
Câu hỏi từ bệnh nhân
        │
        ▼
[1] Đọc Patient Context ──────────────────────────────┐
    (từ hệ thống chung)                                │
        │                                              │
        ▼                                              │
[2] Phân tích Intent & Tạo Query                      │
    - Loại câu hỏi (dinh dưỡng / thuốc / triệu chứng) │
    - Trích xuất entity (tên thuốc, loại thực phẩm)   │
        │                                              │
        ▼                                              │
[3] METADATA-AWARE RETRIEVAL                          │
    - Semantic search (vector similarity)             │
    - Metadata filter (category, source_type,         │
      verified_by_doctor, language)                   │
    - Hybrid re-ranking                               │
        │                                              │
        ▼                                              ▼
[4] Augment Prompt ─────── Context y khoa + Hồ sơ BN
        │
        ▼
[5] Gemini LLM Generate
        │
        ▼
[6] Response + Source Citations
```

---

## 2. Yêu Cầu Chức Năng

### 2.1 FR-01: Metadata-Aware Retrieval

| ID | Yêu cầu | Độ ưu tiên |
|----|---------|-----------|
| FR-01-1 | Mỗi chunk tài liệu phải có metadata đầy đủ (category, source_type, verified, date) | 🔴 Cao |
| FR-01-2 | Hỗ trợ filter theo metadata trước khi semantic search | 🔴 Cao |
| FR-01-3 | Kết hợp semantic score + metadata score để re-rank | 🟡 Trung bình |
| FR-01-4 | Ưu tiên tài liệu đã được bác sĩ xác nhận (`verified_by_doctor = true`) | 🔴 Cao |
| FR-01-5 | Trả về source citation kèm theo mỗi câu trả lời | 🔴 Cao |

### 2.2 FR-02: Quản Lý Tài Liệu

| ID | Yêu cầu | Độ ưu tiên |
|----|---------|-----------|
| FR-02-1 | Admin có thể upload PDF/Word/TXT qua API | 🔴 Cao |
| FR-02-2 | Hệ thống tự động parse, chunk, embed tài liệu mới | 🔴 Cao |
| FR-02-3 | Hiển thị danh sách tài liệu đang có trong Knowledge Base | 🟡 Trung bình |
| FR-02-4 | Xóa/cập nhật tài liệu trong KB mà không phải rebuild toàn bộ | 🟡 Trung bình |
| FR-02-5 | Tự động crawl tài liệu từ các nguồn tin tưởng theo lịch | 🟢 Thấp |

### 2.3 FR-03: Doctor Knowledge Ingestion

| ID | Yêu cầu | Độ ưu tiên |
|----|---------|-----------|
| FR-03-1 | Bác sĩ đăng nhập và thêm "ghi chú y khoa" qua giao diện | 🔴 Cao |
| FR-03-2 | Ghi chú được gán tag: category, condition, verified=true | 🔴 Cao |
| FR-03-3 | Ghi chú của bác sĩ được ưu tiên cao nhất trong retrieval | 🔴 Cao |
| FR-03-4 | Lưu audit log: ai thêm gì, lúc nào | 🟡 Trung bình |
| FR-03-5 | Bác sĩ có thể sửa/xóa ghi chú của mình | 🟡 Trung bình |

### 2.4 FR-04: Tích Hợp Dữ Liệu Bệnh Nhân

| ID | Yêu cầu | Độ ưu tiên |
|----|---------|-----------|
| FR-04-1 | Nhận `patient_context` từ hệ thống chung qua API header/body | 🔴 Cao |
| FR-04-2 | Dùng thông tin BN để cá nhân hóa prompt (tuổi, loại tiểu đường, thuốc đang dùng) | 🔴 Cao |
| FR-04-3 | KHÔNG lưu thông tin cá nhân BN vào Vector DB | 🔴 Cao |
| FR-04-4 | Câu trả lời phải phản ánh tình trạng cụ thể của BN | 🔴 Cao |
| FR-04-5 | Cảnh báo nếu câu hỏi liên quan đến thuốc BN đang dùng | 🟡 Trung bình |

---

## 3. Kiến Trúc Metadata-Aware Retrieval

### 3.1 Ý Tưởng Cốt Lõi

Retrieval thông thường chỉ dùng **semantic similarity** (khoảng cách vector). Metadata-Aware Retrieval bổ sung thêm **bộ lọc và trọng số từ metadata** để tìm đúng loại tài liệu cho từng câu hỏi.

```
CÂU HỎI: "Tôi bị tiểu đường tuýp 2, đang dùng Metformin, 
           sáng nay lỡ ăn 1 bát phở thì nên làm gì?"

SEMANTIC SEARCH (bình thường):
  → Tìm chunks gần nhất với vector của câu hỏi
  → Có thể trả về bài về tiểu đường tuýp 1, bài tiếng Anh,
     hoặc bài cũ chưa được review

METADATA-AWARE (nâng cao):
  Step 1 - PRE-FILTER (bắt buộc đáp ứng):
    category IN ["diet", "blood_glucose", "medication"]
    language = "vi"
  
  Step 2 - SEMANTIC SEARCH trong tập đã filter
    → Lấy top-20 candidates
  
  Step 3 - RE-RANK theo trọng số:
    final_score = 0.7 × semantic_score
                + 0.15 × source_priority_score  (doctor > official > web)
                + 0.10 × recency_score          (mới hơn → ưu tiên hơn)
                + 0.05 × verified_bonus          (đã review → +bonus)
  
  Step 4 - Lấy top-5 chunks có final_score cao nhất
```

### 3.2 Schema Metadata Đầy Đủ

```python
# Mỗi chunk trong ChromaDB có cấu trúc metadata như sau:
CHUNK_METADATA = {
    # --- ĐỊNH DANH ---
    "chunk_id": "vinmec_pho_001",              # ID duy nhất
    "document_id": "vinmec_an_uong_2024",      # ID tài liệu gốc
    "document_title": "Chế độ ăn cho người tiểu đường",
    
    # --- PHÂN LOẠI NỘI DUNG ---
    "category": "diet",                        # Enum: xem bảng bên dưới
    "subcategory": "vietnamese_food",          # Chi tiết hơn
    "diabetes_type": ["type2", "general"],     # type1 | type2 | gestational | general
    "condition_tags": ["obesity", "hypertension"],  # bệnh đi kèm liên quan
    "keywords": ["phở", "GI", "đường huyết", "tinh bột"],
    
    # --- NGUỒN GỐC & ĐỘ TIN CẬY ---
    "source_name": "Vinmec",                   # Tên nguồn
    "source_url": "https://vinmec.com/...",    # URL gốc
    "source_type": "hospital_website",         # Enum: xem bảng bên dưới
    "source_priority": 3,                      # 1=doctor_note | 2=official_guideline | 3=hospital | 4=web
    "verified_by_doctor": True,                # Đã được bác sĩ review
    "verified_by": "Dr. Nguyen Van A",         # Bác sĩ review (nếu có)
    "verified_date": "2024-08-15",
    
    # --- THỜI GIAN ---
    "published_date": "2024-03-01",            # Ngày xuất bản tài liệu gốc
    "indexed_date": "2025-01-10",              # Ngày thêm vào KB
    "last_updated": "2025-01-10",
    
    # --- NGÔN NGỮ & ĐỊA LÝ ---
    "language": "vi",                          # vi | en
    "region": "VN",                           # Phù hợp với thực phẩm Việt Nam
    
    # --- KỸ THUẬT ---
    "chunk_index": 3,                          # Vị trí chunk trong tài liệu
    "total_chunks": 12,                        # Tổng số chunks của tài liệu
    "char_count": 1523,
}
```

### 3.3 Bảng Enum Category

| Giá trị `category` | Mô tả | Ví dụ tài liệu |
|---|---|---|
| `diet` | Chế độ dinh dưỡng | GI thực phẩm, thực đơn mẫu |
| `medication` | Thuốc điều trị | Metformin, Insulin, GLP-1 |
| `blood_glucose` | Theo dõi đường huyết | HbA1c, cách đo, mục tiêu |
| `exercise` | Vận động thể lực | Bài tập, lưu ý an toàn |
| `complication` | Biến chứng | Võng mạc, thận, thần kinh |
| `emergency` | Cấp cứu | Hạ đường huyết, DKA |
| `lifestyle` | Lối sống | Giấc ngủ, stress, bỏ thuốc |
| `diagnosis` | Chẩn đoán | Tiêu chuẩn chẩn đoán, xét nghiệm |
| `general` | Tổng quan | Định nghĩa, phân loại bệnh |

### 3.4 Bảng Enum Source Type

| Giá trị `source_type` | Priority | Ví dụ |
|---|---|---|
| `doctor_note` | 1 (cao nhất) | Ghi chú bác sĩ trong hệ thống |
| `official_guideline` | 2 | ADA 2024, Bộ Y tế VN |
| `hospital_website` | 3 | Vinmec, Bạch Mai, Chợ Rẫy |
| `academic_journal` | 3 | PubMed, Lancet |
| `government_health` | 3 | WHO, CDC |
| `health_website` | 4 | Hellobacsi, Medlatec |
| `web_crawled` | 5 (thấp nhất) | Tài liệu tự crawl chưa review |

### 3.5 Code Triển Khai Metadata-Aware Retrieval

```python
# src/rag/metadata_retriever.py

from dataclasses import dataclass
from typing import Optional
import chromadb

@dataclass
class RetrievalConfig:
    """Cấu hình cho mỗi loại câu hỏi"""
    categories: list[str]           # Chỉ tìm trong các category này
    require_vietnamese: bool = True  # Ưu tiên tiếng Việt
    min_source_priority: int = 5     # 1=chỉ doctor, 5=tất cả nguồn
    require_verified: bool = False   # Chỉ lấy đã được review
    top_k: int = 5
    
    # Trọng số re-ranking (tổng = 1.0)
    w_semantic: float = 0.70
    w_source:   float = 0.15
    w_recency:  float = 0.10
    w_verified: float = 0.05


# Ánh xạ loại câu hỏi → cấu hình retrieval
RETRIEVAL_CONFIGS = {
    "emergency": RetrievalConfig(
        categories=["emergency", "blood_glucose"],
        require_verified=True,
        min_source_priority=3,   # Chỉ nguồn uy tín
        top_k=3,
        w_verified=0.20          # Tăng trọng số verified khi khẩn cấp
    ),
    "medication": RetrievalConfig(
        categories=["medication", "blood_glucose"],
        require_verified=True,
        min_source_priority=3,
        top_k=5
    ),
    "diet": RetrievalConfig(
        categories=["diet", "exercise"],
        require_vietnamese=True,  # Ưu tiên thực phẩm VN
        top_k=5
    ),
    "general": RetrievalConfig(
        categories=["general", "diagnosis", "lifestyle"],
        top_k=5
    ),
}


class MetadataAwareRetriever:
    def __init__(self, collection: chromadb.Collection, embedder):
        self.collection = collection
        self.embedder = embedder

    def detect_intent(self, query: str) -> str:
        """Phát hiện loại câu hỏi từ từ khóa"""
        query_lower = query.lower()
        emergency_kw = ["hôn mê", "ngất", "hạ đường huyết", "run tay", "khẩn cấp",
                        "cấp cứu", "đường huyết thấp", "co giật"]
        medication_kw = ["thuốc", "insulin", "metformin", "tiêm", "liều", "tác dụng phụ"]
        diet_kw = ["ăn", "uống", "thực phẩm", "phở", "cơm", "bún", "bánh", "trái cây",
                   "rau", "gi ", "calo", "đường", "tinh bột"]
        
        if any(kw in query_lower for kw in emergency_kw):
            return "emergency"
        if any(kw in query_lower for kw in medication_kw):
            return "medication"
        if any(kw in query_lower for kw in diet_kw):
            return "diet"
        return "general"

    def build_where_filter(self, config: RetrievalConfig) -> dict:
        """Tạo ChromaDB where filter từ RetrievalConfig"""
        conditions = []
        
        # Filter category
        if config.categories:
            conditions.append({
                "category": {"$in": config.categories}
            })
        
        # Filter source priority
        conditions.append({
            "source_priority": {"$lte": config.min_source_priority}
        })
        
        # Filter language
        if config.require_vietnamese:
            conditions.append({"language": {"$eq": "vi"}})
        
        # Filter verified only
        if config.require_verified:
            conditions.append({"verified_by_doctor": {"$eq": True}})
        
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def compute_source_score(self, source_priority: int) -> float:
        """Chuyển source_priority thành score 0-1"""
        # priority 1 → score 1.0; priority 5 → score 0.2
        return max(0, (6 - source_priority) / 5)

    def compute_recency_score(self, indexed_date: str) -> float:
        """Tài liệu mới hơn → score cao hơn (decay 1 năm)"""
        from datetime import datetime
        try:
            days_old = (datetime.now() - datetime.fromisoformat(indexed_date)).days
            return max(0, 1 - days_old / 365)
        except Exception:
            return 0.5

    def retrieve(self, query: str, patient_context: dict = None) -> list[dict]:
        intent = self.detect_intent(query)
        config = RETRIEVAL_CONFIGS.get(intent, RETRIEVAL_CONFIGS["general"])

        # Nếu có patient_context, điều chỉnh config
        if patient_context:
            diabetes_type = patient_context.get("diabetes_type")
            if diabetes_type:
                # Thêm diabetes_type vào filter (nếu cần)
                pass

        # Bước 1: Pre-filter + Semantic search
        query_vec = self.embedder.encode([query]).tolist()
        where_filter = self.build_where_filter(config)

        results = self.collection.query(
            query_embeddings=query_vec,
            n_results=min(config.top_k * 4, 20),   # Lấy nhiều để re-rank
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        if not results["documents"][0]:
            # Fallback: bỏ filter strict, tìm lại
            results = self.collection.query(
                query_embeddings=query_vec,
                n_results=config.top_k,
                include=["documents", "metadatas", "distances"]
            )

        # Bước 2: Re-rank
        candidates = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            semantic_score = 1 - dist   # cosine distance → similarity
            source_score   = self.compute_source_score(meta.get("source_priority", 5))
            recency_score  = self.compute_recency_score(meta.get("indexed_date", "2024-01-01"))
            verified_bonus = 0.1 if meta.get("verified_by_doctor") else 0

            final_score = (
                config.w_semantic * semantic_score
                + config.w_source  * source_score
                + config.w_recency * recency_score
                + config.w_verified * verified_bonus
            )
            candidates.append({
                "text": doc,
                "metadata": meta,
                "semantic_score": round(semantic_score, 3),
                "final_score": round(final_score, 3),
            })

        # Sắp xếp theo final_score giảm dần
        candidates.sort(key=lambda x: x["final_score"], reverse=True)
        return candidates[:config.top_k]
```

---

## 4. Quy Trình Thu Thập & Quản Lý Tài Liệu

### 4.1 Nguồn Tài Liệu Được Ưu Tiên

```
TIER 1 — Hướng dẫn chính thức (source_priority = 2)
├── ADA Standards of Care 2024 (diabetesjournals.org)
├── IDF Diabetes Atlas 10th Edition (diabetesatlas.org)
├── WHO Diabetes Fact Sheets (who.int)
└── Hướng dẫn điều trị Đái tháo đường — Bộ Y tế VN (moh.gov.vn)

TIER 2 — Bệnh viện & tổ chức y tế uy tín (source_priority = 3)
├── Vinmec (vinmec.com/vie/)
├── Bệnh viện Bạch Mai (bachmai.gov.vn)
├── Bệnh viện Chợ Rẫy (choray.vn)
├── Bệnh viện Nhân dân 115
└── Viện Dinh dưỡng Quốc gia (viendinhduong.vn)

TIER 3 — Trang sức khỏe uy tín VN (source_priority = 4)
├── Hellobacsi (hellobacsi.com)
├── Medlatec (medlatec.vn)
└── YouMed (youmed.vn)
```

### 4.2 Quy Trình Upload Tài Liệu Thủ Công

```
Admin/Bác sĩ có tài liệu PDF/Word/TXT
            │
            ▼
    POST /admin/documents/upload
    {
      file: <file_bytes>,
      metadata: {
        title: "Hướng dẫn ADA 2024",
        source_name: "ADA",
        source_type: "official_guideline",
        category: "medication",
        language: "en",
        published_date: "2024-01-01"
      }
    }
            │
            ▼
    Hệ thống tự động:
    [1] Detect file type (PDF/Word/TXT)
    [2] Extract text (PyMuPDF / python-docx)
    [3] Làm sạch text (remove header, footer, page numbers)
    [4] Chunk text (size=1500, overlap=200)
    [5] Embed từng chunk
    [6] Lưu vào ChromaDB với metadata đầy đủ
    [7] Return: { document_id, chunk_count, status }
```

### 4.3 Cấu Trúc Thư Mục Kho Tài Liệu

```
data/
├── raw/                   # File gốc tải về (không sửa)
│   ├── official/          # Hướng dẫn chính thức
│   ├── hospital/          # Tài liệu bệnh viện
│   └── crawled/           # HTML đã crawl
│
├── processed/             # Text đã extract và làm sạch
│   └── <document_id>.json # { text, metadata }
│
├── pdfs/                  # PDF đã chuẩn hóa (output từ preprocess)
│
├── doctor_notes/          # Ghi chú bác sĩ (Nguồn TIER 1)
│   └── <note_id>.json
│
├── chunks.json            # Tất cả chunks (cache để rebuild nhanh)
│
└── chroma_db/             # ChromaDB vector store
    ├── chroma.sqlite3
    └── <collection_uuid>/
```

---

## 5. Tính Năng Bổ Sung Tri Thức Từ Bác Sĩ

### 5.1 Luồng Bác Sĩ Thêm Tri Thức

```
Bác sĩ đăng nhập vào giao diện admin
            │
            ▼
    Chọn: Thêm ghi chú y khoa
            │
            ▼
    Điền form:
    ┌─────────────────────────────────────┐
    │ Tiêu đề: [Lưu ý về phở và GI]     │
    │                                     │
    │ Nội dung:                           │
    │ [Phở tô lớn chứa ~65-70g carb,    │
    │  tương đương 2 chén cơm. BN T2DM  │
    │  nên chọn tô nhỏ, thêm giá đỗ,   │
    │  hạn chế nước lèo...]             │
    │                                     │
    │ Category: [diet ▼]                  │
    │ Loại tiểu đường: [☑type2 ☐type1]  │
    │ Tags: [phở, GI, tinh bột]         │
    │ Độ ưu tiên: ● Cao ○ Trung bình   │
    └─────────────────────────────────────┘
            │
            ▼
    POST /admin/doctor-notes
    → Tự động embed + lưu ChromaDB
    → source_type = "doctor_note"
    → source_priority = 1
    → verified_by_doctor = True
    → verified_by = "Dr. <tên đăng nhập>"
```

### 5.2 Schema Ghi Chú Bác Sĩ

```json
{
  "note_id": "dr_note_20250115_001",
  "title": "Lưu ý về phở và chỉ số GI cho bệnh nhân T2DM",
  "content": "Phở tô lớn chứa khoảng 65-70g carbohydrate...",
  "author_id": "doctor_nguyen_van_a",
  "author_name": "BS. Nguyễn Văn A",
  "created_at": "2025-01-15T09:30:00",
  "updated_at": "2025-01-15T09:30:00",
  "metadata": {
    "category": "diet",
    "subcategory": "vietnamese_food",
    "diabetes_type": ["type2"],
    "keywords": ["phở", "GI", "tinh bột", "carbohydrate"],
    "source_type": "doctor_note",
    "source_priority": 1,
    "verified_by_doctor": true,
    "verified_by": "BS. Nguyễn Văn A",
    "language": "vi"
  },
  "status": "active",
  "view_count": 0
}
```

### 5.3 API Cho Bác Sĩ

```
POST   /admin/doctor-notes          Thêm ghi chú mới
GET    /admin/doctor-notes          Xem danh sách ghi chú của mình
PUT    /admin/doctor-notes/{id}     Cập nhật ghi chú
DELETE /admin/doctor-notes/{id}     Xóa ghi chú (soft delete)
GET    /admin/doctor-notes/{id}/usage  Xem ghi chú được dùng bao nhiêu lần
```

---

## 6. Tích Hợp Dữ Liệu Bệnh Nhân

### 6.1 Patient Context Schema

Module RAG **không tự lưu** dữ liệu bệnh nhân. Thông tin được truyền từ hệ thống chung vào mỗi request:

```json
{
  "patient_context": {
    "patient_id": "BN_2025_001234",
    
    "demographics": {
      "age": 55,
      "gender": "male",
      "weight_kg": 78,
      "height_cm": 168,
      "bmi": 27.6
    },
    
    "diagnosis": {
      "diabetes_type": "type2",
      "diagnosed_year": 2019,
      "duration_years": 6,
      "complications": ["early_nephropathy", "neuropathy_mild"],
      "comorbidities": ["hypertension", "dyslipidemia"]
    },
    
    "current_medications": [
      { "name": "Metformin", "dose": "1000mg", "frequency": "2x/ngày" },
      { "name": "Gliclazide MR", "dose": "60mg", "frequency": "1x/sáng" },
      { "name": "Lisinopril", "dose": "10mg", "frequency": "1x/ngày" }
    ],
    
    "recent_labs": {
      "hba1c": { "value": 7.8, "unit": "%", "date": "2025-01-01" },
      "fasting_glucose": { "value": 145, "unit": "mg/dL", "date": "2025-01-10" },
      "creatinine": { "value": 1.1, "unit": "mg/dL", "date": "2025-01-01" },
      "egfr": { "value": 68, "unit": "mL/min/1.73m²" }
    },
    
    "glucose_targets": {
      "fasting": "80-130 mg/dL",
      "post_meal": "<180 mg/dL",
      "hba1c_target": "<7.5%"
    },
    
    "dietary_restrictions": ["low_sodium", "low_fat"],
    
    "allergies": ["sulfa_drugs"],
    
    "doctor_notes_for_patient": "BN tuân thủ điều trị tốt, cần giảm thêm 3-5kg"
  }
}
```

### 6.2 Cách Sử Dụng Patient Context Trong Prompt

```python
def build_personalized_prompt(
    query: str,
    retrieved_chunks: list[dict],
    patient_context: dict
) -> str:
    
    ctx = patient_context
    
    # Tóm tắt hồ sơ bệnh nhân cho LLM
    patient_summary = f"""
THÔNG TIN BỆNH NHÂN:
- Tuổi/Giới: {ctx['demographics']['age']} tuổi, {'nam' if ctx['demographics']['gender']=='male' else 'nữ'}
- BMI: {ctx['demographics']['bmi']} kg/m²
- Loại tiểu đường: {ctx['diagnosis']['diabetes_type']} (mắc bệnh {ctx['diagnosis']['duration_years']} năm)
- Biến chứng: {', '.join(ctx['diagnosis']['complications']) or 'chưa có'}
- Bệnh đi kèm: {', '.join(ctx['diagnosis']['comorbidities']) or 'không'}
- Thuốc đang dùng: {', '.join(m['name'] for m in ctx['current_medications'])}
- HbA1c gần nhất: {ctx['recent_labs']['hba1c']['value']}% ({ctx['recent_labs']['hba1c']['date']})
- Đường huyết đói gần nhất: {ctx['recent_labs']['fasting_glucose']['value']} mg/dL
- Mục tiêu HbA1c: {ctx['glucose_targets']['hba1c_target']}
- Hạn chế ăn uống: {', '.join(ctx['dietary_restrictions']) or 'không có'}
- Dị ứng: {', '.join(ctx['allergies']) or 'không có'}
"""

    # Context từ Knowledge Base
    knowledge = "\n\n---\n\n".join(
        f"[Nguồn: {c['metadata']['source_name']}]\n{c['text']}"
        for c in retrieved_chunks
    )
    
    return f"""
[HỒ SƠ BỆNH NHÂN]
{patient_summary}

[TÀI LIỆU Y KHOA THAM KHẢO]
{knowledge}

[CÂU HỎI]
{query}

Hãy trả lời dựa trên tài liệu y khoa và CÁ NHÂN HÓA câu trả lời cho bệnh nhân này.
Lưu ý: bệnh nhân đang dùng {', '.join(m['name'] for m in ctx['current_medications'])}, 
có {ctx['diagnosis']['complications'] or 'chưa'} biến chứng.
Ghi rõ nguồn tham khảo.
"""
```

### 6.3 Cảnh Báo Tương Tác Thuốc Tự Động

```python
DRUG_INTERACTION_RULES = {
    # (thuốc BN đang dùng, nội dung cần cảnh báo)
    ("gliclazide", "rượu"):
        "⚠️ CẢNH BÁO: Bệnh nhân đang dùng Gliclazide. "
        "Uống rượu kết hợp Gliclazide có thể gây hạ đường huyết nghiêm trọng!",
    
    ("metformin", "cản quang"):
        "⚠️ LƯU Ý: Bệnh nhân đang dùng Metformin. "
        "Phải ngừng Metformin 48h trước và sau khi chụp có cản quang.",
    
    ("insulin", "tập thể dục"):
        "💡 CHÚ Ý: Bệnh nhân đang dùng Insulin. "
        "Kiểm tra đường huyết trước khi tập; nguy cơ hạ đường huyết sau tập.",
}

def check_drug_warnings(response_text: str, medications: list[str]) -> list[str]:
    warnings = []
    for (drug, trigger), warning_msg in DRUG_INTERACTION_RULES.items():
        if drug in [m.lower() for m in medications]:
            if trigger in response_text.lower():
                warnings.append(warning_msg)
    return warnings
```

---

## 7. Quy Trình Triển Khai Từng Bước

### 7.1 Roadmap Theo Sprint

```
SPRINT 1 (Tuần 1-2): NỀN TẢNG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ] Cài đặt môi trường (Python venv, dependencies)
[ ] Build Knowledge Base ban đầu (4 file TXT mẫu)
[ ] Implement TF-IDF embedding + ChromaDB cơ bản
[ ] API endpoint /chat hoạt động với Gemini
[ ] Test end-to-end với 10 câu hỏi mẫu

SPRINT 2 (Tuần 3-4): METADATA-AWARE RETRIEVAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ] Định nghĩa và implement schema metadata đầy đủ
[ ] Rebuild ChromaDB với metadata
[ ] Implement MetadataAwareRetriever (pre-filter + re-rank)
[ ] Implement intent detection
[ ] Test A/B: cũ vs mới với 50 câu hỏi mẫu

SPRINT 3 (Tuần 5-6): QUẢN LÝ TÀI LIỆU
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ] API upload tài liệu (PDF/Word/TXT)
[ ] Auto-parse và chunk tài liệu mới
[ ] Crawler crawl tự động từ nguồn tin
[ ] Admin UI: danh sách tài liệu, xóa/cập nhật
[ ] Thu thập thêm 20+ tài liệu y khoa chất lượng

SPRINT 4 (Tuần 7-8): DOCTOR KNOWLEDGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ] Giao diện bác sĩ thêm ghi chú
[ ] API CRUD cho doctor notes
[ ] Audit log
[ ] Test với bác sĩ thực tế

SPRINT 5 (Tuần 9-10): TÍCH HỢP BỆNH NHÂN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ] Nhận patient_context từ hệ thống chung
[ ] Personalized prompt builder
[ ] Drug interaction warnings
[ ] Test với ca bệnh thực tế (anonymized)

SPRINT 6 (Tuần 11-12): PRODUCTION READY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ] Logging và monitoring
[ ] Rate limiting
[ ] Bảo mật: KHÔNG log patient data
[ ] Load testing
[ ] Documentation API
[ ] Deploy staging → production
```

### 7.2 Chi Tiết Bước Cài Đặt

```bash
# === BƯỚC 0: Cài đặt môi trường ===
git clone <repo>
cd healthcare_rag
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# === BƯỚC 1: Cấu hình ===
cp .env.example .env
# Mở .env và điền:
# GEMINI_API_KEY=<key từ aistudio.google.com>
# ADMIN_SECRET_KEY=<tạo ngẫu nhiên>

# === BƯỚC 2: Build Knowledge Base lần đầu ===
python scripts/run_pipeline.py --demo-only
# Hoặc crawl thật:
python scripts/run_pipeline.py

# Kiểm tra kết quả:
python -c "
import chromadb
client = chromadb.PersistentClient('data/chroma_db')
col = client.get_collection('diabetes_knowledge')
print(f'Vectors: {col.count()}')
"

# === BƯỚC 3: Chạy server ===
uvicorn src.api.server:app --reload --port 8000

# === BƯỚC 4: Test ===
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Tôi bị tiểu đường tuýp 2, ăn phở được không?",
    "top_k": 5
  }'
```

---

## 8. Cấu Trúc Dữ Liệu & Schema

### 8.1 Request Schema

```python
# POST /chat
class ChatRequest(BaseModel):
    query: str                          # Câu hỏi (bắt buộc)
    top_k: int = 5                      # Số chunks retrieve (mặc định 5)
    patient_context: Optional[dict]     # Hồ sơ BN từ hệ thống chung
    session_id: Optional[str]           # Để track hội thoại nhiều lượt
    language: str = "vi"               # Ngôn ngữ trả lời

# POST /admin/documents/upload
class DocumentUploadRequest(BaseModel):
    title: str
    source_name: str
    source_type: str                    # Enum: xem bảng 3.4
    category: str                       # Enum: xem bảng 3.3
    language: str = "vi"
    published_date: Optional[str]
    verified_by_doctor: bool = False
```

### 8.2 Response Schema

```python
class ChatResponse(BaseModel):
    answer: str                         # Câu trả lời của AI
    sources: list[SourceCitation]       # Nguồn tham khảo
    warnings: list[str]                 # Cảnh báo tương tác thuốc
    intent_detected: str               # diet | medication | emergency | general
    retrieval_count: int               # Số chunks đã retrieve
    session_id: str
    disclaimer: str = (
        "Thông tin chỉ mang tính tham khảo. "
        "Vui lòng tham khảo ý kiến bác sĩ trước khi thay đổi chế độ điều trị."
    )

class SourceCitation(BaseModel):
    source_name: str                    # "Vinmec", "ADA 2024"...
    document_title: str
    source_url: Optional[str]
    verified_by_doctor: bool
    relevance_score: float             # 0.0 - 1.0
```

---

## 9. API Contract

### 9.1 Endpoint Đầy Đủ

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| GET | `/health` | Public | Kiểm tra server |
| GET | `/stats` | Public | Thống kê KB |
| POST | `/chat` | BN token | Hỏi chatbot |
| POST | `/chat/stream` | BN token | Hỏi với streaming |
| GET | `/search?q=...` | BN token | Tìm trong KB |
| POST | `/admin/documents/upload` | Admin | Upload tài liệu mới |
| GET | `/admin/documents` | Admin | Danh sách tài liệu |
| DELETE | `/admin/documents/{id}` | Admin | Xóa tài liệu |
| POST | `/admin/doctor-notes` | Doctor | Thêm ghi chú |
| GET | `/admin/doctor-notes` | Doctor | Xem ghi chú của mình |
| PUT | `/admin/doctor-notes/{id}` | Doctor | Cập nhật ghi chú |
| DELETE | `/admin/doctor-notes/{id}` | Doctor | Xóa ghi chú |
| POST | `/admin/rebuild-index` | Admin | Rebuild ChromaDB |

### 9.2 Ví Dụ Request Có Patient Context

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <patient_token>" \
  -d '{
    "query": "Sáng nay tôi lỡ ăn 1 tô phở lớn, bây giờ phải làm gì?",
    "top_k": 5,
    "patient_context": {
      "patient_id": "BN_001",
      "demographics": { "age": 55, "gender": "male", "bmi": 27.6 },
      "diagnosis": {
        "diabetes_type": "type2",
        "duration_years": 6,
        "complications": []
      },
      "current_medications": [
        { "name": "Metformin", "dose": "1000mg" },
        { "name": "Gliclazide MR", "dose": "60mg" }
      ],
      "recent_labs": {
        "hba1c": { "value": 7.8, "unit": "%" },
        "fasting_glucose": { "value": 145, "unit": "mg/dL" }
      }
    }
  }'
```

---

## 10. Tiêu Chí Chấp Nhận & Kiểm Thử

### 10.1 Test Cases Cốt Lõi

```
TC-001: Câu hỏi dinh dưỡng cơ bản
  Input: "Người tiểu đường ăn cơm được không?"
  Expected: Câu trả lời đề cập GI của cơm, khuyến nghị cụ thể
  Pass: Có source citation, không hallucinate số liệu

TC-002: Câu hỏi có patient context
  Input: [câu hỏi] + patient_context (đang dùng Gliclazide)
  Expected: Câu trả lời đề cập đến rủi ro hạ đường huyết khi uống rượu
  Pass: Có cảnh báo tương tác thuốc

TC-003: Câu hỏi khẩn cấp
  Input: "Tôi đang run tay, vã mồ hôi, đường huyết đo được 52 mg/dL"
  Expected: Hướng dẫn xử trí ngay (quy tắc 15-15), khuyến nghị gọi bác sĩ
  Pass: Ưu tiên tài liệu verified, trả lời < 3 giây

TC-004: Ghi chú bác sĩ được ưu tiên
  Setup: Thêm doctor note về phở
  Input: "Tôi ăn phở có sao không?"
  Pass: Response tham chiếu đến doctor note trong sources

TC-005: Upload tài liệu mới
  Input: Upload PDF ADA 2024
  Pass: Tài liệu xuất hiện trong danh sách, chunk count > 0,
        câu hỏi liên quan trả về nguồn mới trong vòng 5 phút
```

### 10.2 Metrics Đánh Giá Chất Lượng

| Metric | Mục tiêu | Cách đo |
|--------|----------|---------|
| Retrieval Precision@5 | > 0.75 | % chunks liên quan trong top-5 |
| Answer Faithfulness | > 0.85 | Câu trả lời khớp với context |
| Latency (P95) | < 5 giây | Đo tại server |
| Hallucination rate | < 5% | Review thủ công 100 câu mẫu |
| Source Citation rate | 100% | Mọi câu trả lời phải có nguồn |

---

## 11. Checklist Training & Onboarding

### 11.1 Cho Developer

```
[ ] Đọc và hiểu README.md
[ ] Cài đặt môi trường thành công (python scripts/run_pipeline.py --demo-only)
[ ] Hiểu luồng: Query → Intent → Pre-filter → Semantic Search → Re-rank → LLM
[ ] Biết cách thêm nguồn tài liệu mới vào medical_crawler.py
[ ] Biết cách thêm/sửa metadata schema
[ ] Hiểu cấu trúc patient_context và cách nó ảnh hưởng đến prompt
[ ] Chạy thành công tất cả 5 test cases trong mục 10.1
[ ] Review code MetadataAwareRetriever và hiểu công thức re-ranking
```

### 11.2 Cho Bác Sĩ (Người Bổ Sung Tri Thức)

```
[ ] Đăng nhập vào admin portal thành công
[ ] Thêm 1 ghi chú y khoa mẫu (bất kỳ nội dung)
[ ] Kiểm tra ghi chú xuất hiện khi hỏi câu liên quan
[ ] Biết cách chọn đúng category khi thêm ghi chú
[ ] Biết cách cập nhật/xóa ghi chú
[ ] Hiểu rằng ghi chú được ưu tiên cao nhất trong retrieval
[ ] Quy trình review tài liệu mới từ crawler (xác nhận verified)
```

### 11.3 Cho Admin Hệ Thống

```
[ ] Biết cách upload tài liệu PDF/Word mới
[ ] Hiểu cấu trúc thư mục data/
[ ] Biết khi nào cần chạy python src/rag/indexer.py (rebuild index)
[ ] Cấu hình lịch crawl tự động (cron job)
[ ] Backup ChromaDB định kỳ (copy thư mục data/chroma_db/)
[ ] Monitoring logs tại logs/ để phát hiện lỗi
[ ] Biết cách thêm nguồn mới vào MEDICAL_SOURCES trong crawler
```

---

## Phụ Lục A: Biến Môi Trường

```bash
# .env
GEMINI_API_KEY=xxx            # Bắt buộc - key từ aistudio.google.com
ADMIN_SECRET_KEY=xxx          # Bắt buộc - key bảo vệ admin endpoints
DOCTOR_SECRET_KEY=xxx         # Bắt buộc - key cho bác sĩ

# Cấu hình RAG
TOP_K=5                       # Số chunks retrieve mặc định
CHUNK_SIZE=1500               # Kích thước chunk (ký tự)
CHUNK_OVERLAP=200             # Overlap giữa chunks
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2

# Cấu hình server
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info

# Bảo mật - QUAN TRỌNG
LOG_PATIENT_DATA=false        # KHÔNG BAO GIỜ log thông tin BN
PATIENT_DATA_RETENTION_DAYS=0 # Không lưu patient context
```

---

## Phụ Lục B: Lệnh Thường Dùng

```bash
# Build/rebuild toàn bộ Knowledge Base
python scripts/run_pipeline.py

# Chỉ re-index (sau khi thêm tài liệu mới)
python src/rag/indexer.py

# Kiểm tra số vectors trong DB
python -c "
import chromadb; c = chromadb.PersistentClient('data/chroma_db')
col = c.get_collection('diabetes_knowledge')
print(f'Tổng: {col.count()} vectors')
"

# Chạy server development
uvicorn src.api.server:app --reload --port 8000

# Chạy server production
uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --workers 4

# Xem logs
tail -f logs/app.log

# Backup ChromaDB
cp -r data/chroma_db/ backup/chroma_db_$(date +%Y%m%d)/
```

---

*Tài liệu này nên được cập nhật sau mỗi sprint. Phiên bản kế tiếp: 1.1 sau Sprint 2.*
