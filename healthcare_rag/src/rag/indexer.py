"""
================================================================
BƯỚC 3: INDEXER — Xây Dựng Kho Tri Thức Số (Vector Database)
================================================================

TẠI SAO CẦN BƯỚC NÀY?
  LLM không thể "tra cứu" file PDF trực tiếp. Ta cần:
  1. Đọc PDF → text thuần
  2. Chia text thành chunk nhỏ (~500 token)
  3. Chuyển mỗi chunk thành vector số (embedding)
  4. Lưu vào ChromaDB để tra cứu theo độ tương đồng

EMBEDDING LÀ GÌ?
  Embedding = chuyển đoạn text thành vector số chiều cao
  (ví dụ: 384 chiều). Hai đoạn text có nghĩa gần nhau
  sẽ có vector gần nhau trong không gian.

  "Người tiểu đường nên ăn gì?" ──embedding──► [0.12, -0.34, ...]
  "Chế độ ăn cho bệnh nhân đái tháo đường"  ──embedding──► [0.11, -0.31, ...]
  → Hai vector này gần nhau → tìm được nhau khi search!

LUỒNG:
  data/pdfs/*.pdf
      │
      ▼
  Trích xuất text (PyMuPDF)
      │
      ▼
  Chia chunk (LangChain TextSplitter)
      │
      ▼
  Embed (sentence-transformers multilingual)
      │
      ▼
  Lưu ChromaDB (data/chroma_db/)

CÁCH CHẠY:
  python src/rag/indexer.py
================================================================
"""

import os
import sys
import json
import fitz  # PyMuPDF
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

# LangChain text splitter
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Vector DB
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

# ── Cấu hình ────────────────────────────────────────────────
PDF_DIR          = Path("data/pdfs")
RAW_DIR          = Path("data/raw")
CHROMA_DIR       = Path(os.getenv("CHROMA_PERSIST_DIR", "data/chroma_db"))
COLLECTION_NAME  = "healthcare_diabetes"
USER_KNOWLEDGE_CATEGORY = "user_knowledge"
USER_RESPONSE_RULE_CATEGORY = "user_response_rule"
DOCTOR_NOTE_CATEGORY = "doctor_note"
USER_KNOWLEDGE_SOURCE   = "Người dùng cung cấp"
DOCTOR_NOTE_SOURCE      = "Bac si noi bo"
EMBEDDING_MODEL  = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE", 500))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 50))

CHROMA_DIR.mkdir(parents=True, exist_ok=True)

CATEGORY_ALIASES = {
    "che_do_an": "diet",
    "dieu_tri": "medication",
    "chi_so_duong_huyet": "blood_glucose",
    "tieu_duong_type2": "general",
    "the_duc_loi_song": "lifestyle",
}


def normalize_category(category: str) -> str:
    """Map older Vietnamese folder categories to the metadata schema."""
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
        logger.warning(f"Khong doc duoc metadata raw: {raw_path}")
        return {}


def _metadata_value(value):
    """Chroma metadata accepts scalar values; flatten lists for filtering/display."""
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    if value is None:
        return ""
    return value


def _normalize_note_id(text: str) -> str:
    return hashlib.md5(" ".join(text.split()).encode("utf-8")).hexdigest()[:16]


# ================================================================
# BƯỚC 3A: ĐỌC PDF → TEXT
# ================================================================

def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Trích xuất text từ file PDF dùng PyMuPDF (fitz).

    PyMuPDF nhanh và chính xác hơn pdfplumber cho text thuần.
    Nó giữ lại cấu trúc đoạn văn tốt hơn.

    Args:
        pdf_path: Đường dẫn file PDF

    Returns:
        Text đã trích xuất, các trang ngăn cách bởi '\n\n'
    """
    doc = fitz.open(str(pdf_path))
    pages_text = []

    for page_num, page in enumerate(doc):
        # get_text("text") lấy text thuần, giữ layout tương đối
        text = page.get_text("text")
        if text.strip():
            pages_text.append(text)

    doc.close()
    return "\n\n".join(pages_text)


def load_all_pdfs(pdf_dir: Path) -> List[Dict]:
    """
    Đọc tất cả PDF trong thư mục.

    Returns:
        List[Dict] với keys: content, source, category, filename
    """
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"⚠ Không có file PDF trong {pdf_dir}")
        return []

    documents = []
    logger.info(f"📂 Đọc {len(pdf_files)} file PDF...")

    for pdf_path in tqdm(pdf_files, desc="Đọc PDF"):
        try:
            text = extract_text_from_pdf(pdf_path)
            if not text or len(text) < 100:
                logger.warning(f"  ⚠ Bỏ qua {pdf_path.name} (quá ngắn)")
                continue

            # Phân tích category từ tên file
            # Format: category__source_name.pdf
            stem = pdf_path.stem
            if "__" in stem:
                category, source = stem.split("__", 1)
            else:
                category, source = "unknown", stem

            raw_metadata = _parse_raw_metadata(stem)
            category = normalize_category(raw_metadata.get("category", category))
            source = raw_metadata.get("source_name", source)

            documents.append({
                "content": text,
                "source": source,
                "category": category,
                "filename": pdf_path.name,
                "document_id": stem,
                "title": raw_metadata.get("document_title") or raw_metadata.get("source_name") or stem,
                "source_url": raw_metadata.get("url", ""),
                "source_type": raw_metadata.get("source_type", "document"),
                "source_priority": _safe_int(raw_metadata.get("source_priority"), 4),
                "verified_by_doctor": bool(raw_metadata.get("verified_by_doctor", False)),
                "published_date": raw_metadata.get("published_date", ""),
                "language": raw_metadata.get("language", "vi" if category != "unknown" else ""),
                "condition_tags": raw_metadata.get("condition_tags", []),
            })
            logger.debug(f"  ✓ {pdf_path.name}: {len(text):,} ký tự")

        except Exception as e:
            logger.error(f"  ✗ Lỗi đọc {pdf_path.name}: {e}")

    logger.success(f"✅ Đọc xong {len(documents)} tài liệu")
    return documents


# ================================================================
# BƯỚC 3B: CHIA CHUNK
# ================================================================

def chunk_documents(documents: List[Dict]) -> List[Dict]:
    """
    Chia tài liệu thành các chunk nhỏ để embedding.

    TẠI SAO CẦN CHIA CHUNK?
    - LLM có giới hạn context window (~100k token với Claude)
    - Embedding model có giới hạn nhỏ hơn (~512 token)
    - Chunk nhỏ giúp tìm đúng đoạn liên quan hơn là cả tài liệu

    RecursiveCharacterTextSplitter chia theo thứ tự ưu tiên:
    '\n\n' (đoạn văn) → '\n' (dòng) → '. ' (câu) → ' ' (từ)
    → Cố gắng giữ nguyên cấu trúc ngữ nghĩa

    Args:
        documents: Danh sách tài liệu đã đọc

    Returns:
        Danh sách chunk với metadata đầy đủ
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,           # Tối đa 500 ký tự/chunk
        chunk_overlap=CHUNK_OVERLAP,     # 50 ký tự overlap giữa chunk liên tiếp
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    all_chunks = []
    indexed_date = datetime.now(timezone.utc).date().isoformat()
    for doc in documents:
        # Chia text thành chunks
        chunks = splitter.split_text(doc["content"])

        for i, chunk_text in enumerate(chunks):
            chunk_text = chunk_text.strip()
            if len(chunk_text) < 50:  # Bỏ chunk quá ngắn (vô nghĩa)
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
                    "verified": "true" if doc.get("verified_by_doctor", False) else "false",
                    "published_date": doc.get("published_date", ""),
                    "indexed_date": indexed_date,
                    "language": doc.get("language", ""),
                    "condition_tags": _metadata_value(doc.get("condition_tags", "")),
                    "category": doc["category"],
                    "filename": doc["filename"],
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "char_count": len(chunk_text),
                }
            })

    logger.info(f"📦 Tổng số chunk: {len(all_chunks)}")
    logger.info(f"   (từ {len(documents)} tài liệu, chunk_size={CHUNK_SIZE})")
    return all_chunks


# ================================================================
# BƯỚC 3C: EMBEDDING + LƯU VÀO CHROMADB
# ================================================================

class VectorIndexer:
    """
    Quản lý ChromaDB — lưu và tìm kiếm vector embedding.

    ChromaDB là vector database chạy local, không cần cloud.
    Dữ liệu lưu vào thư mục data/chroma_db/ (persistent).
    """

    def __init__(self):
        logger.info(f"🔌 Kết nối ChromaDB tại: {CHROMA_DIR}")

        # PersistentClient: lưu dữ liệu xuống đĩa (không mất khi tắt)
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )

        # Embedding function: chuyển text → vector
        # paraphrase-multilingual: hỗ trợ 50+ ngôn ngữ kể cả tiếng Việt
        logger.info(f"🧠 Tải embedding model: {EMBEDDING_MODEL}")
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )

        # Tạo hoặc lấy collection (như "bảng" trong database)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embed_fn,
            metadata={
                "description": "Healthcare RAG — Tài liệu y khoa về tiểu đường",
                "hnsw:space": "cosine",  # Dùng cosine similarity để so sánh vector
            }
        )
        logger.success(f"✅ Collection '{COLLECTION_NAME}': {self.collection.count()} document hiện có")

    def index_chunks(self, chunks: List[Dict], batch_size: int = 50):
        """
        Thêm chunks vào ChromaDB.

        Thực hiện theo batch (50 chunk/lần) để:
        - Không tốn quá nhiều RAM
        - Hiển thị tiến độ rõ ràng
        - Dễ retry nếu lỗi

        Args:
            chunks: Danh sách chunk từ chunk_documents()
            batch_size: Số chunk xử lý mỗi lần
        """
        if not chunks:
            logger.warning("⚠ Không có chunk nào để index")
            return

        # Lấy ID đã có để tránh duplicate.
        # Dedupe theo cả DB hiện tại và các chunk mới sinh ra trong cùng lượt index.
        existing_ids = set(self.collection.get()["ids"])
        seen_ids = set(existing_ids)
        logger.info(f"📊 Đã có {len(existing_ids)} chunks trong DB")

        # Chuẩn bị dữ liệu cho ChromaDB
        new_ids, new_texts, new_metadatas = [], [], []

        for i, chunk in enumerate(chunks):
            # Tạo ID ổn định theo document + chunk_index + hash nội dung.
            # Cách này tránh trùng giữa các chunk có text giống nhau nhưng thuộc
            # tài liệu khác nhau, đồng thời vẫn idempotent khi crawl lại cùng file.
            metadata = chunk.get("metadata", {})
            document_id = str(metadata.get("document_id") or metadata.get("source") or "document")
            chunk_index = metadata.get("chunk_index", i)
            chunk_hash = hashlib.md5(" ".join(chunk["text"].split()).encode("utf-8")).hexdigest()[:16]
            full_id = f"{document_id}__chunk_{chunk_index}__{chunk_hash}"

            if full_id in seen_ids:
                continue  # Bỏ qua chunk đã có

            seen_ids.add(full_id)
            new_ids.append(full_id)
            new_texts.append(chunk["text"])
            new_metadatas.append(chunk["metadata"])

        if not new_ids:
            logger.info("⏭ Tất cả chunks đã được index rồi!")
            return

        logger.info(f"📥 Đang index {len(new_ids)} chunks mới...")

        # Chia thành batch và index
        for i in tqdm(range(0, len(new_ids), batch_size), desc="Indexing"):
            batch_ids   = new_ids[i:i+batch_size]
            batch_texts = new_texts[i:i+batch_size]
            batch_metas = new_metadatas[i:i+batch_size]

            # ChromaDB không cho phép duplicate ids trong cùng một lần add().
            batch_seen = set()
            unique_ids, unique_texts, unique_metas = [], [], []
            for doc_id, text, meta in zip(batch_ids, batch_texts, batch_metas):
                if doc_id in batch_seen:
                    continue
                batch_seen.add(doc_id)
                unique_ids.append(doc_id)
                unique_texts.append(text)
                unique_metas.append(meta)

            if not unique_ids:
                continue

            self.collection.add(
                ids=unique_ids,
                documents=unique_texts,   # ChromaDB sẽ tự embed qua embed_fn
                metadatas=unique_metas,
            )

        total = self.collection.count()
        logger.success(f"✅ Index xong! Tổng cộng {total} chunks trong ChromaDB")

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
        condition_tags: Optional[List[str]] = None,
        filename: str = "",
        replace_existing: bool = True,
    ) -> Dict:
        clean_text = " ".join(text.split())
        if not clean_text:
            raise ValueError("Uploaded document is empty")

        doc = {
            "content": clean_text,
            "source": source_name or title or document_id,
            "category": normalize_category(category),
            "filename": filename or f"{document_id}.txt",
            "document_id": document_id,
            "title": title or source_name or document_id,
            "source_url": source_url,
            "source_type": source_type,
            "source_priority": source_priority if source_priority is not None else (3 if verified_by_doctor else 4),
            "verified_by_doctor": verified_by_doctor,
            "published_date": published_date,
            "language": language,
            "condition_tags": condition_tags or [normalize_category(category)],
        }

        if replace_existing:
            self.collection.delete(where={"document_id": {"$eq": document_id}})

        chunks = chunk_documents([doc])
        if not chunks:
            return {"document_id": document_id, "chunks_indexed": 0, "replaced": replace_existing}

        self.index_chunks(chunks)
        return {
            "document_id": document_id,
            "chunks_indexed": len(chunks),
            "replaced": replace_existing,
        }

    def add_user_knowledge(
        self,
        text: str,
        category: str = USER_KNOWLEDGE_CATEGORY,
        knowledge_type: str = "knowledge",
    ) -> Dict:
        """
        Luu thong tin nguoi dung gop y vao ChromaDB nhu mot nguon rieng.

        Thong tin nay duoc gan nhan source_type=user va verified=false de
        prompt khong xem no la tai lieu y khoa chinh thuc.
        """
        clean_text = " ".join(text.split())
        chunk_id = hashlib.md5(clean_text.encode("utf-8")).hexdigest()[:16]
        id_prefix = "user_rule" if category == USER_RESPONSE_RULE_CATEGORY else "user_knowledge"
        full_id = f"{id_prefix}__{chunk_id}"
        metadata = {
            "source": USER_KNOWLEDGE_SOURCE,
            "category": category,
            "filename": "user_feedback",
            "chunk_index": 0,
            "total_chunks": 1,
            "source_type": "user",
            "knowledge_type": knowledge_type,
            "verified": "false",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        existing = self.collection.get(ids=[full_id])
        if existing.get("ids"):
            return {"id": full_id, "metadata": metadata, "duplicate": True}

        self.collection.add(
            ids=[full_id],
            documents=[clean_text],
            metadatas=[metadata],
        )
        logger.info(f"Đã ghi nhớ thông tin người dùng: {full_id}")
        return {"id": full_id, "metadata": metadata, "duplicate": False}

    def add_doctor_note(
        self,
        text: str,
        category: str,
        doctor_name: str,
        specialty: str = "",
        note_id: Optional[str] = None,
        status: str = "active",
    ) -> Dict:
        clean_text = " ".join(text.split())
        note_id = note_id or f"doctor_note__{_normalize_note_id(clean_text)}"
        metadata = {
            "document_id": note_id,
            "document_title": f"Doctor note - {doctor_name}".strip(),
            "source": DOCTOR_NOTE_SOURCE,
            "category": category,
            "filename": "doctor_notes",
            "chunk_index": 0,
            "total_chunks": 1,
            "source_type": "doctor_note",
            "source_priority": 1,
            "verified_by_doctor": True,
            "verified": "true",
            "doctor_name": doctor_name,
            "specialty": specialty,
            "note_status": status,
            "language": "vi",
            "published_date": datetime.now(timezone.utc).date().isoformat(),
            "indexed_date": datetime.now(timezone.utc).isoformat(),
        }

        existing = self.collection.get(ids=[note_id])
        if existing.get("ids"):
            self.collection.update(
                ids=[note_id],
                documents=[clean_text],
                metadatas=[metadata],
            )
            return {"id": note_id, "metadata": metadata, "duplicate": False, "updated": True}

        self.collection.add(
            ids=[note_id],
            documents=[clean_text],
            metadatas=[metadata],
        )
        logger.info(f"Đã thêm doctor note: {note_id}")
        return {"id": note_id, "metadata": metadata, "duplicate": False, "updated": False}

    def delete_document(self, doc_id: str) -> bool:
        existing = self.collection.get(ids=[doc_id])
        if not existing.get("ids"):
            return False
        self.collection.delete(ids=[doc_id])
        return True

    def search(
        self,
        query: str,
        top_k: int = 5,
        category_filter: str = None,
        where_filter: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Tìm kiếm chunks liên quan đến câu hỏi.

        Quy trình:
        1. Embed câu hỏi thành vector
        2. Tìm top_k vector gần nhất trong DB (cosine similarity)
        3. Trả về text + metadata

        Args:
            query: Câu hỏi của user
            top_k: Số kết quả trả về
            category_filter: Lọc theo danh mục (tuỳ chọn)

        Returns:
            Danh sách dict: text, metadata, distance
        """
        if category_filter:
            category_where = {"category": {"$eq": category_filter}}
            where_filter = (
                {"$and": [where_filter, category_where]}
                if where_filter
                else category_where
            )

        count = self.collection.count()
        if count == 0:
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, count),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        # Format kết quả
        hits = []
        for i, (doc_id, doc, meta, dist) in enumerate(zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )):
            hits.append({
                "id": doc_id,
                "rank": i + 1,
                "text": doc,
                "metadata": meta,
                "similarity": round(1 - dist, 4),  # Chuyển distance → similarity
            })

        return hits

    def get_stats(self) -> dict:
        """Thống kê về collection hiện tại."""
        try:
            count = self.collection.count()
            if not isinstance(count, int) or count == 0:
                return {"total_chunks": 0, "categories": {}}

            # Lấy sample metadata để thống kê
            sample = self.collection.get(limit=min(count, 1000), include=["metadatas"])
            
            # Validate sample response
            if not sample or "metadatas" not in sample:
                return {"total_chunks": count, "categories": {}}
            
            categories = {}
            metadatas = sample.get("metadatas", [])
            if not isinstance(metadatas, list):
                metadatas = []
            
            for meta in metadatas:
                if isinstance(meta, dict):
                    cat = meta.get("category", "unknown")
                    categories[cat] = categories.get(cat, 0) + 1

            return {
                "total_chunks": count,
                "categories": categories,
                "embedding_model": EMBEDDING_MODEL,
                "chunk_size": CHUNK_SIZE,
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"total_chunks": 0, "categories": {}, "error": str(e)}


# ── CHẠY TRỰC TIẾP ──────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🗃 INDEXER — Xây Dựng Vector Database")
    logger.info("=" * 60)

    # Bước 1: Đọc PDF
    documents = load_all_pdfs(PDF_DIR)
    if not documents:
        logger.error("❌ Không có tài liệu. Hãy chạy pdf_builder.py trước!")
        sys.exit(1)

    # Bước 2: Chia chunk
    chunks = chunk_documents(documents)

    # Bước 3: Index vào ChromaDB
    indexer = VectorIndexer()
    indexer.index_chunks(chunks)

    # Thống kê
    stats = indexer.get_stats()
    logger.info(f"\n📊 THỐNG KÊ VECTOR DATABASE:")
    logger.info(f"   Tổng chunks  : {stats['total_chunks']}")
    logger.info(f"   Theo danh mục:")
    for cat, count in stats["categories"].items():
        logger.info(f"     - {cat}: {count} chunks")

    # Test search
    logger.info("\n🔍 Test tìm kiếm:")
    test_query = "Người tiểu đường type 2 ăn phở được không?"
    indexer_test = VectorIndexer()
    hits = indexer_test.search(test_query, top_k=3)
    logger.info(f"Query: '{test_query}'")
    for hit in hits:
        logger.info(f"  #{hit['rank']} [{hit['similarity']:.3f}] {hit['metadata']['source']}: {hit['text'][:100]}...")

    logger.success("\n✅ Index xong! Vector DB sẵn sàng.")
    logger.info("▶  Bước tiếp theo: python src/rag/pipeline.py")
