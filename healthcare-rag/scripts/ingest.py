"""
scripts/ingest.py
──────────────────
Index tất cả tài liệu trong data/pdfs/ vào Qdrant.

Dùng:
  python scripts/ingest.py
  python scripts/ingest.py --incremental
  python scripts/ingest.py --dir data/pdfs/complication
"""
from __future__ import annotations

import argparse
import json
import hashlib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from loguru import logger
from src.chunking.chunker import chunk_documents
from src.ingestion.loader import load_all_documents
from src.vectordb.vector_store import VectorStore
from src.utils.config import cfg

STATE_FILE = ROOT / ".ingest_state.json"


def _load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _file_hash(path: Path) -> str:
    stat = path.stat()
    return hashlib.md5(f"{path}:{stat.st_size}:{stat.st_mtime}".encode()).hexdigest()


def ingest(pdf_dir: Path, incremental: bool = False):
    logger.info("=" * 60)
    logger.info("📥 INGEST — Đẩy tài liệu vào Qdrant")
    logger.info("=" * 60)
    logger.info(f"  Thư mục: {pdf_dir.resolve()}")
    logger.info(f"  Mode: {'incremental' if incremental else 'full'}")

    if incremental:
        state = _load_state()
        all_files = list(pdf_dir.rglob("*.pdf")) + list(pdf_dir.rglob("*.txt"))
        new_files = [f for f in all_files if state.get(str(f)) != _file_hash(f)]
        logger.info(f"  {len(all_files)} file tổng, {len(new_files)} file mới/thay đổi")
        if not new_files:
            logger.success("✅ Không có file mới. Qdrant đã up-to-date!")
            return
        # Tạo thư mục tạm để load chỉ file mới
        # → đơn giản hơn: load tất cả rồi filter bằng state
        docs = [d for d in load_all_documents(pdf_dir)
                if any(str(pdf_dir / d["filename"]) in str(f) for f in new_files)]
        if not docs:
            # Fallback: load tất cả
            docs = load_all_documents(pdf_dir)
    else:
        state = {}
        docs = load_all_documents(pdf_dir)

    if not docs:
        logger.error("❌ Không có tài liệu nào")
        sys.exit(1)

    logger.info(f"\n[2/3] Chunking {len(docs)} tài liệu...")
    chunks = chunk_documents(docs)
    logger.info(f"  → {len(chunks)} chunks")

    logger.info("\n[3/3] Upsert vào Qdrant...")
    t0 = time.time()
    vs = VectorStore()
    vs.upsert_chunks(chunks)
    elapsed = time.time() - t0

    # Update state
    if incremental:
        for f in pdf_dir.rglob("*.pdf"):
            state[str(f)] = _file_hash(f)
        for f in pdf_dir.rglob("*.txt"):
            state[str(f)] = _file_hash(f)
        _save_state(state)

    stats = vs.get_stats()
    logger.success(f"\n✅ INGEST XONG! ({elapsed:.1f}s)")
    logger.info(f"   Tổng chunks: {stats['total_chunks']}")
    logger.info("   Phân loại:")
    for cat, cnt in sorted(stats.get("categories", {}).items(), key=lambda x: -x[1]):
        logger.info(f"     {cat:<25}: {cnt:>5} chunks")
    logger.info("\n🌐 Qdrant dashboard: http://localhost:6333/dashboard")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=str(cfg.paths.pdf_dir))
    parser.add_argument("--incremental", action="store_true")
    args = parser.parse_args()
    ingest(Path(args.dir), incremental=args.incremental)
