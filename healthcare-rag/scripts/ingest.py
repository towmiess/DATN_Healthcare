"""
================================================================
INGEST — Index PDF và TXT vào Qdrant
================================================================

Hỗ trợ:
  - PDF  → extract text bằng PyMuPDF
  - TXT  → đọc trực tiếp (format từ crawler.py)
  - Tài liệu ngắn KHÔNG bị bỏ qua — vẫn được index

CÁCH DÙNG:
  # Index tất cả PDF + TXT trong data/pdfs/:
  python scripts/ingest.py

  # Chỉ index file mới (chưa được index):
  python scripts/ingest.py --incremental

  # Index thư mục cụ thể:
  python scripts/ingest.py --dir data/pdfs/complication

  # Crawl trước rồi ingest luôn:
  python scripts/crawler.py --ingest
================================================================
"""

import sys
import argparse
import json
import hashlib
import time
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))

from loguru import logger
from dotenv import load_dotenv
load_dotenv()

from src.rag.indexer import (
    VectorIndexer, chunk_documents, extract_text_from_pdf,
    _parse_raw_metadata, normalize_category, _safe_int,
)

STATE_FILE = ROOT / ".ingest_state.json"


def _load_state() -> Dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: Dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _file_hash(path: Path) -> str:
    stat = path.stat()
    return hashlib.md5(f"{path}:{stat.st_size}:{stat.st_mtime}".encode()).hexdigest()


def _extract_text_from_txt(txt_path: Path) -> tuple[str, Dict]:
    """
    Đọc file TXT (từ crawler).
    Format có thể có ===METADATA=== / ===CONTENT=== header.
    Trả về (content_text, metadata_dict).
    """
    raw = txt_path.read_text(encoding="utf-8", errors="replace")
    meta = {}
    if "===METADATA===" in raw and "===CONTENT===" in raw:
        meta_part, content_part = raw.split("===CONTENT===", 1)
        meta_text = meta_part.replace("===METADATA===", "").strip()
        try:
            meta = json.loads(meta_text)
        except json.JSONDecodeError:
            pass
        text = content_part.strip()
    else:
        text = raw.strip()
    return text, meta


def load_all_documents(pdf_dir: Path) -> List[Dict]:
    """
    Đọc tất cả PDF và TXT trong thư mục.
    Tài liệu ngắn KHÔNG bị bỏ qua — chỉ log cảnh báo.
    """
    pdf_files = sorted(pdf_dir.rglob("*.pdf"))
    txt_files = sorted(pdf_dir.rglob("*.txt"))
    # Bỏ qua .gitkeep và hidden files
    txt_files = [f for f in txt_files if not f.name.startswith(".") and f.stat().st_size > 10]

    all_files = pdf_files + txt_files
    if not all_files:
        logger.warning(f"⚠ Không có file PDF/TXT trong {pdf_dir}")
        return []

    logger.info(f"📂 Tìm thấy {len(pdf_files)} PDF + {len(txt_files)} TXT = {len(all_files)} file")

    from tqdm import tqdm
    from datetime import datetime, timezone

    documents = []
    skipped_empty = 0
    short_docs = 0

    for file_path in tqdm(all_files, desc="Đọc tài liệu"):
        try:
            # ── Đọc text ──────────────────────────────────
            raw_meta_from_file = {}
            if file_path.suffix.lower() == ".pdf":
                text = extract_text_from_pdf(file_path)
                raw_meta_from_file = _parse_raw_metadata(file_path.stem)
            else:
                text, raw_meta_from_file = _extract_text_from_txt(file_path)

            if not text or not text.strip():
                logger.warning(f"  ⚠ Bỏ qua {file_path.name} — không có text")
                skipped_empty += 1
                continue

            char_count = len(text.strip())
            if char_count < 20:
                logger.warning(f"  ⚠ Bỏ qua {file_path.name} — quá ngắn ({char_count} ký tự, có thể scan-only)")
                skipped_empty += 1
                continue

            if char_count < 300:
                logger.info(f"  📄 Tài liệu ngắn: {file_path.name} ({char_count} ký tự) — vẫn index")
                short_docs += 1

            # ── Xác định category ─────────────────────────
            stem = file_path.stem
            if "__" in stem:
                category_from_name, source_from_name = stem.split("__", 1)
            else:
                try:
                    rel = file_path.relative_to(pdf_dir)
                    parts = rel.parts
                    if len(parts) >= 3:
                        # complication/cardiovascular/file.pdf → cardiovascular
                        category_from_name = parts[-2]
                    elif len(parts) >= 2:
                        category_from_name = parts[0]
                    else:
                        category_from_name = "unknown"
                except ValueError:
                    category_from_name = "unknown"
                source_from_name = stem

            # Ưu tiên metadata từ file, fallback sang tên file/folder
            category = normalize_category(
                raw_meta_from_file.get("category", category_from_name)
            )
            source = raw_meta_from_file.get("source_name", source_from_name)
            language = raw_meta_from_file.get("language", "vi")

            documents.append({
                "content": text,
                "source": source,
                "category": category,
                "filename": file_path.name,
                "document_id": stem,
                "title": raw_meta_from_file.get("document_title") or raw_meta_from_file.get("title") or stem,
                "source_url": raw_meta_from_file.get("url", ""),
                "source_type": raw_meta_from_file.get("source_type", "document"),
                "source_priority": _safe_int(raw_meta_from_file.get("source_priority"), 4),
                "verified_by_doctor": bool(raw_meta_from_file.get("verified_by_doctor", False)),
                "published_date": raw_meta_from_file.get("published_date", ""),
                "language": language,
            })

        except Exception as e:
            logger.error(f"  ✗ Lỗi đọc {file_path.name}: {e}")

    logger.success(
        f"✅ Đọc xong {len(documents)} tài liệu "
        f"(bỏ qua {skipped_empty} rỗng, {short_docs} tài liệu ngắn được giữ lại)"
    )
    return documents


def ingest_all(pdf_dir: Path, incremental: bool = False):
    logger.info("=" * 60)
    logger.info("📥 INGEST — Đẩy tài liệu vào Qdrant")
    logger.info("=" * 60)
    logger.info(f"  Thư mục: {pdf_dir.resolve()}")
    logger.info(f"  Mode: {'incremental (chỉ file mới)' if incremental else 'full'}")

    state = _load_state() if incremental else {}

    # Thu thập tất cả file
    pdf_files = sorted(pdf_dir.rglob("*.pdf"))
    txt_files = sorted(pdf_dir.rglob("*.txt"))
    txt_files = [f for f in txt_files if not f.name.startswith(".") and f.stat().st_size > 10]
    all_files = pdf_files + txt_files

    if not all_files:
        logger.error(f"❌ Không có file PDF/TXT trong {pdf_dir}")
        sys.exit(1)

    logger.info(f"  {len(pdf_files)} PDF + {len(txt_files)} TXT = {len(all_files)} file tổng")

    # Filter incremental
    if incremental:
        new_files = [f for f in all_files if state.get(str(f)) != _file_hash(f)]
        logger.info(f"  {len(new_files)} file mới/thay đổi")
        if not new_files:
            logger.success("✅ Không có file mới. Qdrant đã up-to-date!")
            return
        to_process = new_files
    else:
        to_process = all_files

    # Đọc documents
    logger.info(f"\n[1/3] Đọc {len(to_process)} tài liệu...")
    documents = load_all_documents(pdf_dir if not incremental else pdf_dir)

    # Khi incremental, chỉ lấy docs từ to_process
    if incremental:
        to_process_names = {f.stem for f in to_process}
        documents = [d for d in documents if d["document_id"] in to_process_names]

    if not documents:
        logger.error("❌ Không đọc được tài liệu nào")
        sys.exit(1)

    logger.info(f"\n[2/3] Chunking {len(documents)} tài liệu...")
    chunks = chunk_documents(documents)
    logger.info(f"  → {len(chunks)} chunks")

    logger.info("\n[3/3] Upsert vào Qdrant...")
    t0 = time.time()
    vi = VectorIndexer()
    vi.index_chunks(chunks)
    elapsed = time.time() - t0

    # Cập nhật state
    if incremental:
        for f in to_process:
            state[str(f)] = _file_hash(f)
        _save_state(state)

    stats = vi.get_stats()
    logger.success(f"\n✅ INGEST XONG! ({elapsed:.1f}s)")
    logger.info(f"   Tổng chunks: {stats['total_chunks']:,}")
    logger.info("   Phân loại:")
    for cat, cnt in sorted(stats.get("categories", {}).items(), key=lambda x: -x[1]):
        logger.info(f"     {cat:<25}: {cnt:>5} chunks")
    logger.info("\n🌐 Xem trực quan: http://localhost:6333/dashboard")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest PDF + TXT vào Qdrant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python scripts/ingest.py                      # Index tất cả
  python scripts/ingest.py --incremental        # Chỉ file mới/thay đổi
  python scripts/ingest.py --dir data/pdfs/diet # Chỉ index folder diet
        """
    )
    parser.add_argument("--dir", default="data/pdfs", help="Thư mục PDF/TXT")
    parser.add_argument("--incremental", action="store_true", help="Chỉ index file mới")
    args = parser.parse_args()

    ingest_all(Path(args.dir), incremental=args.incremental)