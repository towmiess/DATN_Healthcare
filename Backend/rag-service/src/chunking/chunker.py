"""
src/chunking/chunker.py
───────────────────────
Chia tài liệu thành chunks phù hợp cho RAG y tế.

Chiến lược:
  - Tài liệu dài (>50k ký tự) dùng chunk_size x2 để giữ ngữ cảnh y văn
  - Separators ưu tiên đoạn văn → dòng → câu → từ
  - Bỏ chunk dưới min_chunk_chars (chỉ số, header rỗng...)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from src.utils.config import cfg

_CHUNK_SIZE    = cfg.chunking.chunk_size
_CHUNK_OVERLAP = cfg.chunking.chunk_overlap
_MIN_CHARS     = cfg.chunking.min_chunk_chars
_LONG_DOC_THRESHOLD = 50_000   # ký tự


def chunk_documents(documents: List[Dict]) -> List[Dict]:
    """
    Nhận list tài liệu, trả về list chunks với đầy đủ metadata.

    Mỗi chunk dict:
        text      : nội dung đoạn văn
        metadata  : {document_id, source, category, language, ...}
    """
    all_chunks: list[Dict] = []
    indexed_date = datetime.now(timezone.utc).date().isoformat()

    for doc in documents:
        content = doc.get("content", "")
        if not content:
            continue

        # Tài liệu dài → tăng chunk_size để giữ ngữ cảnh y văn
        is_long = len(content) > _LONG_DOC_THRESHOLD
        chunk_size = min(_CHUNK_SIZE * 2, 1_800) if is_long else _CHUNK_SIZE

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=_CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        raw_chunks = splitter.split_text(content)
        valid_chunks = [c.strip() for c in raw_chunks if len(c.strip()) >= _MIN_CHARS]

        for i, chunk_text in enumerate(valid_chunks):
            all_chunks.append({
                "text": chunk_text,
                "metadata": {
                    "document_id":      doc.get("document_id", doc.get("filename", "")),
                    "document_title":   doc.get("title", doc.get("source", "")),
                    "source":           doc.get("source", ""),
                    "source_url":       doc.get("source_url", ""),
                    "source_type":      doc.get("source_type", "document"),
                    "source_priority":  int(doc.get("source_priority", 4)),
                    "verified_by_doctor": bool(doc.get("verified_by_doctor", False)),
                    "published_date":   doc.get("published_date", ""),
                    "indexed_date":     indexed_date,
                    "language":         doc.get("language", "vi"),
                    "category":         doc.get("category", "general"),
                    "filename":         doc.get("filename", ""),
                    "chunk_index":      i,
                    "total_chunks":     len(valid_chunks),
                    "char_count":       len(chunk_text),
                },
            })

    logger.info(f"📦 Tổng số chunk: {len(all_chunks)}")
    return all_chunks
