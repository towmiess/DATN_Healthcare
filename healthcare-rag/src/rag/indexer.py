"""
================================================================
INDEXER — Xây Dựng Vector Database với Qdrant
================================================================

Thay ChromaDB bằng Qdrant:
  - Hiệu năng cao hơn, hỗ trợ filtering tốt hơn
  - Có Web UI tại http://localhost:6333/dashboard
  - Dễ migrate lên cloud (Qdrant Cloud / AWS)

LUỒNG:
  data/pdfs/**/*.pdf
      │
      ▼
  PyMuPDF → text
      │
      ▼
  LangChain TextSplitter → chunks
      │
      ▼
  sentence-transformers (multilingual) → vectors
      │
      ▼
  Qdrant collection "healthcare_diabetes"

CÁCH CHẠY:
  # Local (ngoài Docker, Qdrant chạy qua docker-compose):
  python scripts/ingest.py

  # Hoặc chạy trực tiếp:
  python src/rag/indexer.py
================================================================
"""

import os
import sys
import json
import fitz  # PyMuPDF
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from sentence_transformers import SentenceTransformer

# ── Cấu hình ────────────────────────────────────────────────
PDF_DIR         = Path(os.getenv("PDF_DIR", "data/pdfs"))
RAW_DIR         = Path("data/raw")
QDRANT_URL      = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY  = os.getenv("QDRANT_API_KEY", "")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "healthcare_diabetes")
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
# Chunk size tối ưu cho tài liệu y khoa:
# - 800-1000 ký tự đủ để giữ 1 đoạn y văn có ngữ cảnh hoàn chỉnh
# - Overlap 150 để không mất thông tin ở ranh giới chunk
CHUNK_SIZE      = int(os.getenv("CHUNK_SIZE", 900))
CHUNK_OVERLAP   = int(os.getenv("CHUNK_OVERLAP", 150))
VECTOR_SIZE     = 384  # paraphrase-multilingual-MiniLM-L12-v2 output dim

USER_KNOWLEDGE_CATEGORY     = "user_knowledge"
USER_RESPONSE_RULE_CATEGORY = "user_response_rule"
DOCTOR_NOTE_CATEGORY        = "doctor_note"

CATEGORY_ALIASES = {
    "che_do_an":       "diet",
    "dieu_tri":        "medication",
    "chi_so_duong_huyet": "blood_glucose",
    "tieu_duong_type2": "general",
    "the_duc_loi_song": "lifestyle",
    # Biến chứng
    "bien_chung":      "complication",
    "tim_mach":        "cardiovascular",
    "than":            "nephropathy",
    "mat_bien_chung":  "retinopathy",
    "than_kinh":       "neuropathy",
    "ban_chan":        "foot_care",
    "complication":    "complication",
    "cardiovascular":  "cardiovascular",
    "nephropathy":     "nephropathy",
    "retinopathy":     "retinopathy",
    "neuropathy":      "neuropathy",
    "foot_care":       "foot_care",
}



# ── Smart category từ tên file (cho file không có prefix __) ─
KEYWORD_TO_CATEGORY = {
    # ADA chapters
    "ada_1.": "general",      "ada_2.": "diagnosis",
    "ada_3.": "lifestyle",    "ada_4.": "diagnosis",
    "ada_5.": "lifestyle",    "ada_6.": "blood_glucose",
    "ada_7.": "blood_glucose","ada_8.": "lifestyle",
    "ada_9.": "medication",   "ada_10.": "cardiovascular",
    "ada_11.": "nephropathy", "ada_12.": "retinopathy",
    "ada_13.": "general",     "ada_14.": "general",
    "ada_15.": "pregnancy",   "ada_16.": "general",
    "ada_17.": "general",
    "ada_introduction": "general", "ada_summary": "general",
    # Biến chứng
    "cardiovascular": "cardiovascular", "cardiac": "cardiovascular",
    "heart": "cardiovascular", "stroke": "cardiovascular", "cvd": "cardiovascular",
    "retinopathy": "retinopathy", "eye_disease": "retinopathy",
    "neuropathy": "neuropathy", "nerve_damage": "neuropathy",
    "foot_care": "foot_care", "foot_problem": "foot_care", "ban_chan": "foot_care",
    "nephropathy": "nephropathy", "kidney": "nephropathy",
    "renal": "nephropathy", "ckd": "nephropathy", "kdigo": "nephropathy",
    # Thai kỳ
    "pregnancy": "pregnancy", "thai_ky": "pregnancy",
    "prenatal": "pregnancy", "postnatal": "pregnancy", "gestation": "pregnancy",
    # Thuốc
    "pharmacolog": "medication", "medication": "medication",
    "insulin": "medication", "metformin": "medication",
    "ng28": "medication", "nice_type2": "medication",
    "drug_therapy": "medication", "dieu_tri": "medication",
    # Đường huyết
    "glycemic": "blood_glucose", "blood_glucose": "blood_glucose",
    "blood_sugar": "blood_glucose", "duong_huyet": "blood_glucose",
    "hba1c": "blood_glucose", "glucose_monitor": "blood_glucose",
    # Cấp cứu
    "hypoglycemi": "emergency", "low_blood_sugar": "emergency",
    "low_blood_glucose": "emergency", "ha_duong": "emergency",
    "emergency": "emergency", "saca_disaster": "emergency", "disaster": "emergency",
    # Chẩn đoán
    "diagnosis": "diagnosis", "chan_doan": "diagnosis",
    "classification": "diagnosis", "screening": "diagnosis",
    # Chế độ ăn
    "diet": "diet", "che_do_an": "diet", "nutrition": "diet",
    "eating_plan": "diet", "dinh_duong": "diet", "healthy_eating": "diet",
    # Lối sống
    "lifestyle": "lifestyle", "exercise": "lifestyle", "the_duc": "lifestyle",
    "loi_song": "lifestyle", "obesity": "lifestyle", "weight_management": "lifestyle",
    "physical_activity": "lifestyle",
    # Khác
    "mental_health": "general", "mental": "general",
}


def _smart_category_from_name(stem: str, folder_hint: str = "") -> str:
    """
    Detect category từ tên file bằng keyword matching.
    Ưu tiên: folder hint (cardiovascular, nephropathy...) > keyword trong stem.
    """
    # Subfolder hint rõ ràng → dùng luôn
    EXPLICIT_FOLDERS = {
        "cardiovascular", "nephropathy", "neuropathy",
        "retinopathy", "foot_care", "pregnancy",
        "blood_glucose", "diagnosis", "diet",
        "medication", "emergency", "lifestyle", "general",
    }
    if folder_hint and folder_hint in EXPLICIT_FOLDERS:
        return folder_hint

    # Keyword matching trên stem
    s = stem.lower().replace("-", "_").replace(" ", "_")
    # Ưu tiên match dài trước (tránh "heart" match trước "heart_disease")
    for kw in sorted(KEYWORD_TO_CATEGORY.keys(), key=len, reverse=True):
        if kw.lower().replace("-", "_") in s:
            return KEYWORD_TO_CATEGORY[kw]

    # Folder hint không explicit → dùng làm fallback
    if folder_hint and folder_hint not in ("diabetes", "unknown", ""):
        return folder_hint

    return "general"

def normalize_category(category: str) -> str:
    return CATEGORY_ALIASES.get((category or "unknown").strip(), category or "unknown")


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_raw_metadata(stem: str) -> Dict:
    raw_path = RAW_DIR / f"{stem}.txt"
    if not raw_path.exists():
        return {}
    text = raw_path.read_text(encoding="utf-8")
    if "===METADATA===" not in text or "===CONTENT===" not in text:
        return {}
    meta_part = text.split("===CONTENT===", 1)[0].replace("===METADATA===", "").strip()
    try:
        return json.loads(meta_part)
    except json.JSONDecodeError:
        return {}


# ================================================================
# BƯỚC A: ĐỌC PDF → TEXT
# ================================================================

def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text từ PDF.
    - Thử PyMuPDF trước (nhanh, đủ với PDF text-based).
    - Nếu rỗng → thử OCR bằng pytesseract (cho PDF scan/image).
    - Fallback: trả về chuỗi rỗng.
    """
    # ── Bước 1: PyMuPDF (text layer) ─────────────────────────
    pymupdf_result = ""
    try:
        doc = fitz.open(str(pdf_path))
        pages_text = []
        for page in doc:
            # Thử rawdict để lấy text chính xác hơn với font đặc biệt
            try:
                blocks = page.get_text("dict")["blocks"]
                page_text = ""
                for block in blocks:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            page_text += span.get("text", "")
                        page_text += "\n"
                    page_text += "\n"
            except Exception:
                page_text = page.get_text("text")

            if page_text.strip():
                pages_text.append(page_text)
        doc.close()
        pymupdf_result = "\n\n".join(pages_text)
    except Exception as e:
        logger.debug(f"PyMuPDF lỗi {pdf_path.name}: {e}")

    # Kiểm tra text có bị lỗi font (garbled Vietnamese) không
    if pymupdf_result.strip() and not _is_garbled_vietnamese(pymupdf_result):
        return pymupdf_result
    elif pymupdf_result.strip():
        logger.info(f"  🔧 Phát hiện lỗi font: {pdf_path.name} → chuyển sang OCR")
    # Nếu rỗng hoặc garbled → thử OCR

    # ── Bước 2: OCR bằng pytesseract ─────────────────────────
    try:
        import pytesseract
        from pdf2image import convert_from_path

        logger.info(f"  🔍 OCR: {pdf_path.name}")
        # Convert PDF → list of PIL images (300 DPI đủ tốt cho y văn)
        images = convert_from_path(str(pdf_path), dpi=200, first_page=1, last_page=20)
        ocr_texts = []
        for img in images:
            # Thử tiếng Anh + tiếng Việt
            text = pytesseract.image_to_string(img, lang="eng+vie", config="--psm 3")
            if text.strip():
                ocr_texts.append(text)
        result = "\n\n".join(ocr_texts)
        if result.strip():
            logger.success(f"  ✅ OCR thành công: {pdf_path.name} ({len(result)} ký tự)")
            return result
        else:
            logger.warning(f"  ⚠ OCR không ra text: {pdf_path.name} (có thể ảnh chất lượng thấp)")
            return ""
    except ImportError:
        logger.debug("pytesseract/pdf2image chưa cài — bỏ qua OCR")
        return ""
    except Exception as e:
        logger.warning(f"  ⚠ OCR lỗi {pdf_path.name}: {e}")
        return ""



def _is_garbled_vietnamese(text: str) -> bool:
    """
    Phát hiện text bị lỗi font (reportlab/VNI/TCVN3).
    Pattern: 'IIIng'=ường, 'ThIc'=Thực, 'TiIu'=Tiểu, 'bIu'=bầu
    """
    if not text or len(text) < 50:
        return False
    import re
    sample = text[:2000]
    # Pattern đặc trưng của font lỗi tiếng Việt
    specific = [
        "IIIng", "ThIc", "TiIu", "bIu", "mInh",
        "sIng", "trIa", "IIng", "GIi", "ThIc",
        "nIi", "kIe", "vIt", "IIn ",
    ]
    count = sum(sample.count(p) for p in specific)
    if count >= 3:
        return True
    # Fallback ratio
    garbled = len(re.findall(r"[a-z]I[A-Z]|[A-Z]{2,}[a-z]{1,2}I", sample))
    words = len(sample.split())
    return words > 0 and (garbled / words) > 0.12


def _detect_language(text: str, filename: str = "") -> str:
    """Tự detect ngôn ngữ từ tên file và nội dung."""
    # Ưu tiên 1: tên file có chứa hint ngôn ngữ
    fname = filename.lower()
    if any(x in fname for x in ["_en_", "_en.", "-en-", "-en.", "english", "_eng"]):
        return "en"
    if any(x in fname for x in ["_vi_", "_vi.", "-vi-", "-vi.", "viet", "vn_", "_vn."]):
        return "vi"

    # Ưu tiên 1.5: tên file PDF khoa học tiếng Anh
    en_filename_hints = [
        "kdigo", "ada_", "dc24", "dc26", "nice", "who_",
        "niddk", "ncbi", "pubmed", "springer", "nature",
        "lancet", "nejm", "jama", "bmj", "idf",
    ]
    if any(h in fname for h in en_filename_hints):
        return "en"

    # Ưu tiên 2: kiểm tra ký tự tiếng Việt trong 500 ký tự đầu
    sample = text[:500]
    viet_chars = set("àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ")
    viet_count = sum(1 for c in sample.lower() if c in viet_chars)
    if viet_count > 5:
        return "vi"

    # Ưu tiên 3: từ tiếng Anh phổ biến trong y tế
    en_keywords = ["diabetes", "glucose", "insulin", "patient", "treatment", "management",
                   "blood", "clinical", "therapy", "the ", "and ", "of ", "for ", "with "]
    en_count = sum(1 for kw in en_keywords if kw in sample.lower())
    if en_count >= 3:
        return "en"

    return "vi"  # default


def load_all_pdfs(pdf_dir: Path) -> List[Dict]:
    """Đọc tất cả PDF trong thư mục và subfolder."""
    pdf_files = sorted(pdf_dir.rglob("*.pdf"))
    if not pdf_files:
        logger.warning(f"⚠ Không có file PDF trong {pdf_dir}")
        return []

    documents = []
    logger.info(f"📂 Đọc {len(pdf_files)} file PDF...")

    for pdf_path in tqdm(pdf_files, desc="Đọc PDF"):
        try:
            text = extract_text_from_pdf(pdf_path)
            if not text or len(text) < 20:
                logger.warning(f"  ⚠ Bỏ qua {pdf_path.name} (rỗng hoặc scan-only)")
                continue
            if len(text) < 100:
                logger.info(f"  📄 Tài liệu ngắn: {pdf_path.name} ({len(text)} ký tự) — vẫn index")

            stem = pdf_path.stem

            # Xác định folder hint
            try:
                rel = pdf_path.relative_to(pdf_dir)
                if len(rel.parts) >= 3:
                    folder_hint = rel.parts[-2]   # e.g. "cardiovascular", "nephropathy"
                elif len(rel.parts) >= 2:
                    folder_hint = rel.parts[0]    # e.g. "diabetes", "complication"
                else:
                    folder_hint = ""
            except ValueError:
                folder_hint = ""

            # Source name
            if "__" in stem:
                source = stem.split("__", 1)[1]
            else:
                source = stem

            # Smart detect category từ tên file + folder
            raw_metadata = _parse_raw_metadata(stem)
            if raw_metadata.get("category"):
                category = normalize_category(raw_metadata["category"])
            else:
                category = _smart_category_from_name(stem, folder_hint)

            source = raw_metadata.get("source_name", source)

            documents.append({
                "content": text,
                "source": source,
                "category": category,
                "filename": pdf_path.name,
                "document_id": stem,
                "title": raw_metadata.get("document_title") or stem,
                "source_url": raw_metadata.get("url", ""),
                "source_type": raw_metadata.get("source_type", "document"),
                "source_priority": _safe_int(raw_metadata.get("source_priority"), 4),
                "verified_by_doctor": bool(raw_metadata.get("verified_by_doctor", False)),
                "published_date": raw_metadata.get("published_date", ""),
                "language": raw_metadata.get("language") or _detect_language(text, pdf_path.name),
            })

        except Exception as e:
            logger.error(f"  ✗ Lỗi đọc {pdf_path.name}: {e}")

    logger.success(f"✅ Đọc xong {len(documents)} tài liệu")
    return documents


# ================================================================
# BƯỚC B: CHIA CHUNK
# ================================================================

def chunk_documents(documents: List[Dict]) -> List[Dict]:
    all_chunks = []
    indexed_date = datetime.now(timezone.utc).date().isoformat()

    for doc in documents:
        # Tài liệu dài (>50k ký tự) như ADA Standards, KDIGO → chunk lớn hơn
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE if len(doc.get("content", "")) < 50000 else min(CHUNK_SIZE * 2, 1800),
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks = splitter.split_text(doc["content"])
        for i, chunk_text in enumerate(chunks):
            chunk_text = chunk_text.strip()
            if len(chunk_text) < 50:
                continue
            all_chunks.append({
                "text": chunk_text,
                "metadata": {
                    "document_id": doc.get("document_id", doc["filename"]),
                    "document_title": doc.get("title", doc["source"]),
                    "source": doc["source"],
                    "source_url": doc.get("source_url", ""),
                    "source_type": doc.get("source_type", "document"),
                    "source_priority": _safe_int(doc.get("source_priority"), 4),
                    "verified_by_doctor": bool(doc.get("verified_by_doctor", False)),
                    "published_date": doc.get("published_date", ""),
                    "indexed_date": indexed_date,
                    "language": doc.get("language", "vi"),
                    "category": doc["category"],
                    "filename": doc["filename"],
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "char_count": len(chunk_text),
                }
            })

    logger.info(f"📦 Tổng số chunk: {len(all_chunks)}")
    return all_chunks


# ================================================================
# BƯỚC C: VECTOR INDEXER (Qdrant)
# ================================================================

class VectorIndexer:
    """
    Quản lý Qdrant — embed và tìm kiếm chunks.

    Qdrant khác ChromaDB:
      - Lưu vector + payload (metadata) riêng biệt
      - Phải embed text trước khi upsert (không embed tự động)
      - Dùng PointStruct với UUID làm id
    """

    def __init__(self):
        logger.info(f"🔌 Kết nối Qdrant tại: {QDRANT_URL}")

        kwargs = {"url": QDRANT_URL, "timeout": 30}
        if QDRANT_API_KEY:
            kwargs["api_key"] = QDRANT_API_KEY

        self.client = QdrantClient(**kwargs)

        logger.info(f"🧠 Tải embedding model: {EMBEDDING_MODEL}")
        self.encoder = SentenceTransformer(EMBEDDING_MODEL)

        self._ensure_collection()
        count = self._count()
        logger.success(f"✅ Collection '{COLLECTION_NAME}': {count} vectors hiện có")

    def _ensure_collection(self):
        """Tạo collection nếu chưa có."""
        existing = [c.name for c in self.client.get_collections().collections]
        if COLLECTION_NAME not in existing:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"  ✅ Tạo collection mới: {COLLECTION_NAME}")

    def _count(self) -> int:
        try:
            info = self.client.get_collection(COLLECTION_NAME)
            return info.points_count or 0
        except Exception:
            return 0

    def _embed(self, texts: List[str]) -> List[List[float]]:
        """Embed danh sách text → list of vectors."""
        vectors = self.encoder.encode(texts, show_progress_bar=False)
        return vectors.tolist()

    def _make_point_id(self, document_id: str, chunk_index: int, text: str) -> str:
        """Tạo UUID ổn định từ document_id + chunk_index + hash text."""
        raw = f"{document_id}__{chunk_index}__{text[:50]}"
        return str(uuid.UUID(hashlib.md5(raw.encode()).hexdigest()))

    def index_chunks(self, chunks: List[Dict], batch_size: int = 64):
        """Upsert chunks vào Qdrant theo batch."""
        if not chunks:
            logger.warning("⚠ Không có chunk nào để index")
            return 0

        points = []
        for chunk in chunks:
            meta = chunk["metadata"]
            point_id = self._make_point_id(
                meta.get("document_id", ""),
                meta.get("chunk_index", 0),
                chunk["text"],
            )
            points.append({
                "id": point_id,
                "text": chunk["text"],
                "payload": meta,
            })

        logger.info(f"📥 Đang index {len(points)} chunks vào Qdrant...")

        upserted = 0
        for i in tqdm(range(0, len(points), batch_size), desc="Indexing"):
            batch = points[i:i + batch_size]
            texts = [p["text"] for p in batch]
            vectors = self._embed(texts)

            qdrant_points = [
                PointStruct(
                    id=p["id"],
                    vector=v,
                    payload={**p["payload"], "text": p["text"]},
                )
                for p, v in zip(batch, vectors)
            ]
            self.client.upsert(
                collection_name=COLLECTION_NAME,
                points=qdrant_points,
            )
            upserted += len(batch)

        total = self._count()
        logger.success(f"✅ Index xong! Tổng {total} vectors trong Qdrant")
        return upserted

    def search(
        self,
        query: str,
        top_k: int = 5,
        category_filter: Optional[str] = None,
        where_filter: Optional[Dict] = None,
    ) -> List[Dict]:
        """Tìm kiếm semantic trong Qdrant."""
        count = self._count()
        if count == 0:
            return []

        query_vector = self._embed([query])[0]

        # Build filter
        qdrant_filter = None
        if category_filter:
            qdrant_filter = Filter(
                must=[FieldCondition(
                    key="category",
                    match=MatchValue(value=category_filter),
                )]
            )

        results = self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=min(top_k, count),
            query_filter=qdrant_filter,
            with_payload=True,
        )

        hits = []
        for i, r in enumerate(results):
            payload = r.payload or {}
            hits.append({
                "id": str(r.id),
                "rank": i + 1,
                "text": payload.pop("text", ""),
                "metadata": payload,
                "similarity": round(float(r.score), 4),
            })

        return hits

    def index_uploaded_document(
        self,
        *,
        text: str,
        document_id: str,
        title: str,
        source_name: str,
        source_type: str,
        category: str,
        language: str = "vi",
        published_date: str = "",
        verified_by_doctor: bool = False,
        source_url: str = "",
        source_priority: Optional[int] = None,
        filename: str = "",
        replace_existing: bool = True,
    ) -> Dict:
        clean_text = " ".join(text.split())
        if not clean_text:
            raise ValueError("Document rỗng")

        if replace_existing:
            # Xóa tất cả chunks của document này
            self.client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=Filter(
                    must=[FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )]
                ),
            )

        doc = {
            "content": clean_text,
            "source": source_name or title or document_id,
            "category": normalize_category(category),
            "filename": filename or f"{document_id}.txt",
            "document_id": document_id,
            "title": title or document_id,
            "source_url": source_url,
            "source_type": source_type,
            "source_priority": source_priority if source_priority is not None else 4,
            "verified_by_doctor": verified_by_doctor,
            "published_date": published_date,
            "language": language,
        }
        chunks = chunk_documents([doc])
        if not chunks:
            return {"document_id": document_id, "chunks_indexed": 0}

        self.index_chunks(chunks)
        return {"document_id": document_id, "chunks_indexed": len(chunks)}

    def add_user_knowledge(
        self,
        text: str,
        category: str = USER_KNOWLEDGE_CATEGORY,
        knowledge_type: str = "knowledge",
    ) -> Dict:
        clean_text = " ".join(text.split())
        chunk_hash = hashlib.md5(clean_text.encode()).hexdigest()[:16]
        id_prefix = "user_rule" if category == USER_RESPONSE_RULE_CATEGORY else "user_knowledge"
        point_id = self._make_point_id(id_prefix, 0, clean_text)

        vector = self._embed([clean_text])[0]
        payload = {
            "text": clean_text,
            "source": "Người dùng cung cấp",
            "category": category,
            "filename": "user_feedback",
            "source_type": "user",
            "knowledge_type": knowledge_type,
            "verified_by_doctor": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        logger.info(f"Đã ghi nhớ thông tin người dùng: {chunk_hash}")
        return {"id": point_id, "duplicate": False}

    def get_stats(self) -> Dict:
        try:
            count = self._count()
            if count == 0:
                return {"total_chunks": 0, "categories": {}}

            # Scroll để lấy sample metadata (max 1000)
            results, _ = self.client.scroll(
                collection_name=COLLECTION_NAME,
                limit=min(count, 1000),
                with_payload=True,
                with_vectors=False,
            )
            categories = {}
            for point in results:
                cat = (point.payload or {}).get("category", "unknown")
                categories[cat] = categories.get(cat, 0) + 1

            return {
                "total_chunks": count,
                "categories": categories,
                "embedding_model": EMBEDDING_MODEL,
                "chunk_size": CHUNK_SIZE,
            }
        except Exception as e:
            logger.error(f"Lỗi get_stats: {e}")
            return {"total_chunks": 0, "categories": {}, "error": str(e)}


# ── CHẠY TRỰC TIẾP ──────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🗃 INDEXER — Xây Dựng Vector Database (Qdrant)")
    logger.info("=" * 60)

    documents = load_all_pdfs(PDF_DIR)
    if not documents:
        logger.error("❌ Không có tài liệu nào!")
        sys.exit(1)

    chunks = chunk_documents(documents)
    indexer = VectorIndexer()
    indexer.index_chunks(chunks)

    stats = indexer.get_stats()
    logger.info(f"\n📊 THỐNG KÊ:")
    logger.info(f"   Tổng chunks: {stats['total_chunks']}")
    for cat, cnt in stats.get("categories", {}).items():
        logger.info(f"     - {cat}: {cnt}")

    logger.success("\n✅ Index xong! Truy cập http://localhost:6333/dashboard để xem.")