"""
src/vectordb/vector_store.py
─────────────────────────────
Qdrant operations: upsert, search, delete, stats.

Tách hoàn toàn khỏi logic embed/chunk/load —
chỉ biết về vector + payload.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Dict, List, Optional

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from tqdm import tqdm

from src.embeddings.embedder import get_embedder
from src.utils.config import cfg

# ── Constants ──────────────────────────────────────────────────
USER_KNOWLEDGE_CATEGORY     = "user_knowledge"
USER_RESPONSE_RULE_CATEGORY = "user_response_rule"
DOCTOR_NOTE_CATEGORY        = "doctor_note"

_COLLECTION = cfg.qdrant.collection
_VECTOR_SIZE = cfg.embedding.vector_size
_BATCH_SIZE  = 64


def _make_point_id(document_id: str, chunk_index: int, text: str) -> str:
    raw = f"{document_id}__{chunk_index}__{text[:50]}"
    return str(uuid.UUID(hashlib.md5(raw.encode()).hexdigest()))


class VectorStore:
    """
    Low-level Qdrant wrapper.
    Tidak ada logika bisnis di sini — hanya operasi DB.
    """

    def __init__(self):
        kwargs: dict = {"url": cfg.qdrant.url, "timeout": 30}
        if cfg.qdrant.api_key:
            kwargs["api_key"] = cfg.qdrant.api_key

        logger.info(f"🔌 Kết nối Qdrant tại: {cfg.qdrant.url}")
        self.client = QdrantClient(**kwargs)
        self._embedder = None
        self._ensure_collection()

        count = self._count()
        logger.success(f"✅ Collection '{_COLLECTION}': {count} vectors hiện có")

    # ── Collection lifecycle ──────────────────────────────────

    def _ensure_collection(self) -> None:
        existing = {c.name for c in self.client.get_collections().collections}
        if _COLLECTION not in existing:
            self.client.create_collection(
                collection_name=_COLLECTION,
                vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info(f"  ✅ Tạo collection mới: {_COLLECTION}")

    def _count(self) -> int:
        try:
            info = self.client.get_collection(_COLLECTION)
            return info.points_count or 0
        except Exception:
            return 0

    def _get_embedder(self):
        if self._embedder is None:
            self._embedder = get_embedder()
        return self._embedder

    # ── Write ─────────────────────────────────────────────────

    def upsert_chunks(self, chunks: List[Dict], batch_size: int = _BATCH_SIZE) -> int:
        """
        Upsert chunks (với text + metadata) vào Qdrant.

        Args:
            chunks: List[Dict] từ chunker.chunk_documents()
            batch_size: số chunk mỗi batch embed + upsert

        Returns:
            Số chunk đã upsert.
        """
        if not chunks:
            logger.warning("⚠ Không có chunk nào để index")
            return 0

        logger.info(f"📥 Đang index {len(chunks)} chunks vào Qdrant...")
        upserted = 0

        for i in tqdm(range(0, len(chunks), batch_size), desc="Indexing"):
            batch = chunks[i: i + batch_size]
            texts = [c["text"] for c in batch]
            vectors = self._get_embedder().encode(texts)

            points = []
            for chunk, vector in zip(batch, vectors):
                meta = chunk["metadata"]
                pid = _make_point_id(
                    meta.get("document_id", ""),
                    meta.get("chunk_index", 0),
                    chunk["text"],
                )
                points.append(
                    PointStruct(
                        id=pid,
                        vector=vector,
                        payload={**meta, "text": chunk["text"]},
                    )
                )

            self.client.upsert(collection_name=_COLLECTION, points=points)
            upserted += len(batch)

        total = self._count()
        logger.success(f"✅ Index xong! Tổng {total} vectors trong Qdrant")
        return upserted

    def delete_by_document_id(self, document_id: str) -> None:
        """Xóa tất cả chunks của một tài liệu."""
        self.client.delete(
            collection_name=_COLLECTION,
            points_selector=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            ),
        )
        logger.info(f"🗑 Đã xóa document: {document_id}")

    def upsert_single(
        self,
        text: str,
        payload: Dict,
        point_id: Optional[str] = None,
    ) -> str:
        """Upsert một chunk đơn lẻ (user knowledge, doctor note...)."""
        if point_id is None:
            point_id = _make_point_id(
                payload.get("document_id", "manual"),
                0,
                text,
            )
        vector = self._get_embedder().encode([text])[0]
        self.client.upsert(
            collection_name=_COLLECTION,
            points=[PointStruct(id=point_id, vector=vector, payload={**payload, "text": text})],
        )
        return point_id

    def upsert_user_knowledge(
        self,
        text: str,
        source: str = "user",
        added_by: str = "user",
        note: str = "",
    ) -> str:
        """Lưu tri thức VĨNH VIỄN — không gắn session_id, áp dụng cho mọi session."""
        from datetime import datetime, timezone
        payload = {
            "document_id": "user_knowledge__global",
            "category": USER_KNOWLEDGE_CATEGORY,
            "source": source,
            "source_type": "user_memory",
            "title": "User provided knowledge",
            "language": "vi",
            "verified_by_doctor": False,
            "source_priority": 1,
            "published_date": "",
            "added_by": added_by,
            "note": note,
            "indexed_date": datetime.now(timezone.utc).date().isoformat(),
        }
        return self.upsert_single(text=text, payload=payload)

    def upsert_user_response_rule(
        self,
        text: str,
        source: str = "user",
        added_by: str = "user",
        note: str = "",
    ) -> str:
        """Lưu luật trả lời do người dùng dạy — áp dụng cho mọi session."""
        from datetime import datetime, timezone
        payload = {
            "document_id": "user_response_rule__global",
            "category": USER_RESPONSE_RULE_CATEGORY,
            "source": source,
            "source_type": "user_memory",
            "title": "User provided response rule",
            "language": "vi",
            "verified_by_doctor": False,
            "source_priority": 1,
            "published_date": "",
            "added_by": added_by,
            "note": note,
            "indexed_date": datetime.now(timezone.utc).date().isoformat(),
        }
        return self.upsert_single(text=text, payload=payload)

    # ── Read ──────────────────────────────────────────────────

    def search_user_knowledge(self, query: str, top_k: int = 3) -> List[Dict]:
        """Tìm tri thức người dùng liên quan — global, không filter theo session."""
        return self.search(
            query,
            top_k=top_k,
            qdrant_filter=Filter(must=[
                FieldCondition(key="category", match=MatchValue(value=USER_KNOWLEDGE_CATEGORY))
            ]),
        )

    def search_user_response_rule(self, query: str, top_k: int = 3) -> List[Dict]:
        """Tìm luật trả lời người dùng liên quan — global, không filter theo session."""
        return self.search(
            query,
            top_k=top_k,
            qdrant_filter=Filter(must=[
                FieldCondition(key="category", match=MatchValue(value=USER_RESPONSE_RULE_CATEGORY))
            ]),
        )

    def list_user_knowledge(self) -> List[Dict]:
        """Liệt kê tất cả tri thức user đã lưu (dùng cho admin endpoint)."""
        try:
            results, _ = self.client.scroll(
                collection_name=_COLLECTION,
                scroll_filter=Filter(must=[
                    FieldCondition(key="category", match=MatchValue(value=USER_KNOWLEDGE_CATEGORY))
                ]),
                limit=200,
                with_payload=True,
                with_vectors=False,
            )
            return [
                {
                    "id": str(r.id),
                    "text": r.payload.get("text", ""),
                    "metadata": {k: v for k, v in r.payload.items() if k != "text"},
                }
                for r in results
            ]
        except Exception as exc:
            logger.warning(f"list_user_knowledge error: {exc}")
            return []

    def list_user_response_rules(self) -> List[Dict]:
        """Liệt kê toàn bộ luật trả lời user đã lưu."""
        try:
            results, _ = self.client.scroll(
                collection_name=_COLLECTION,
                scroll_filter=Filter(must=[
                    FieldCondition(key="category", match=MatchValue(value=USER_RESPONSE_RULE_CATEGORY))
                ]),
                limit=200,
                with_payload=True,
                with_vectors=False,
            )
            return [
                {
                    "id": str(r.id),
                    "text": r.payload.get("text", ""),
                    "metadata": {k: v for k, v in r.payload.items() if k != "text"},
                }
                for r in results
            ]
        except Exception as exc:
            logger.warning(f"list_user_response_rules error: {exc}")
            return []

    def delete_user_knowledge(self, point_id: str) -> None:
        """Xóa một mẩu tri thức cụ thể theo point_id."""
        from qdrant_client.http.models import PointIdsList
        self.client.delete(
            collection_name=_COLLECTION,
            points_selector=PointIdsList(points=[point_id]),
        )
        logger.info(f"🗑 Đã xóa user knowledge point: {point_id}")

    def clear_user_knowledge(self) -> None:
        """Xóa TOÀN BỘ tri thức user (dùng thận trọng)."""
        self.client.delete(
            collection_name=_COLLECTION,
            points_selector=Filter(must=[
                FieldCondition(key="category", match=MatchValue(value=USER_KNOWLEDGE_CATEGORY))
            ]),
        )
        logger.info("🗑 Đã xóa toàn bộ user knowledge")

    def clear_user_response_rules(self) -> None:
        """Xóa TOÀN BỘ luật trả lời user (dùng thận trọng)."""
        self.client.delete(
            collection_name=_COLLECTION,
            points_selector=Filter(must=[
                FieldCondition(key="category", match=MatchValue(value=USER_RESPONSE_RULE_CATEGORY))
            ]),
        )
        logger.info("🗑 Đã xóa toàn bộ user response rules")

    def search(
        self,
        query: str,
        top_k: int = 5,
        qdrant_filter: Optional[Filter] = None,
    ) -> List[Dict]:
        """
        Semantic search.

        Returns:
            List[Dict] với keys: id, rank, text, metadata, similarity
        """
        count = self._count()
        if count == 0:
            return []

        query_vector = self._get_embedder().encode([query])[0]
        results = self.client.search(
            collection_name=_COLLECTION,
            query_vector=query_vector,
            limit=min(top_k, count),
            query_filter=qdrant_filter,
            with_payload=True,
        )

        hits = []
        for rank, r in enumerate(results, 1):
            payload = dict(r.payload or {})
            text = payload.pop("text", "")
            hits.append({
                "id":         str(r.id),
                "rank":       rank,
                "text":       text,
                "metadata":   payload,
                "similarity": round(float(r.score), 4),
            })
        return hits

    # ── Stats ────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        try:
            count = self._count()
            if count == 0:
                return {"total_chunks": 0, "categories": {}}

            results, _ = self.client.scroll(
                collection_name=_COLLECTION,
                limit=min(count, 1_000),
                with_payload=True,
                with_vectors=False,
            )
            categories: Dict[str, int] = {}
            for point in results:
                cat = (point.payload or {}).get("category", "unknown")
                categories[cat] = categories.get(cat, 0) + 1

            return {
                "total_chunks":    count,
                "categories":      categories,
                "embedding_model": cfg.embedding.model,
                "chunk_size":      cfg.chunking.chunk_size,
            }
        except Exception as exc:
            logger.error(f"Lỗi get_stats: {exc}")
            return {"total_chunks": 0, "categories": {}, "error": str(exc)}
