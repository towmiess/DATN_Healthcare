#!/usr/bin/env python3
"""
================================================================
SCRIPT CHẠY TOÀN BỘ PIPELINE — 1 lệnh để setup mọi thứ
================================================================

Lệnh:  python scripts/run_pipeline.py

Sẽ thực hiện theo thứ tự:
  [1] Crawl tài liệu y khoa → data/raw/
  [2] Build PDF chuẩn hóa  → data/pdfs/
  [3] Index Vector DB       → data/chroma_db/
  [4] Khởi động API server  → http://localhost:8000

Flags:
  --skip-crawl    Bỏ qua bước crawl (dùng data/raw/ có sẵn)
  --skip-pdf      Bỏ qua bước build PDF
  --skip-index    Bỏ qua bước index
  --no-server     Không khởi động server
  --demo-only     Chỉ tạo dữ liệu mẫu (không crawl internet)
================================================================
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path
from loguru import logger

# Chạy từ thư mục gốc project
ROOT = Path(__file__).parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))


def print_step(n: int, title: str):
    logger.info(f"\n{'='*60}")
    logger.info(f"  BƯỚC {n}: {title}")
    logger.info(f"{'='*60}")


def check_env():
    """Kiểm tra .env và API key."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        example = ROOT / ".env.example"
        if example.exists():
            import shutil
            shutil.copy(example, env_file)
            logger.warning("⚠ Đã copy .env.example → .env")
            logger.warning("  Hãy điền GEMINI_API_KEY vào file .env trước khi chạy server!")
        return False

    from dotenv import load_dotenv
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    if not key or key.lower().startswith(("xxx", "your_", "your-")):
        logger.warning("⚠ GEMINI_API_KEY chưa được cấu hình trong .env")
        logger.warning("  Crawler và PDF builder vẫn chạy được, nhưng chatbot cần API key.")
        return False
    return True


def step1_crawl(skip: bool = False, demo_only: bool = False):
    """Bước 1: Crawl tài liệu y khoa."""
    print_step(1, "CRAWL TÀI LIỆU Y KHOA")

    if skip:
        logger.info("⏭ Bỏ qua bước crawl (--skip-crawl)")
        return True

    # Kiểm tra đã có raw data chưa
    raw_files = list((ROOT / "data/raw").glob("*.txt"))
    real_files = [f for f in raw_files if f.name != "crawl_metadata.json"]

    if real_files and not demo_only:
        logger.info(f"📁 Đã có {len(real_files)} file trong data/raw/")
        ans = input("  Crawl lại không? (y/N): ").strip().lower()
        if ans != 'y':
            logger.info("  ⏭ Dùng data cũ")
            return True

    if demo_only:
        logger.info("📝 Chế độ demo: Tạo dữ liệu mẫu (không crawl internet)")
        from src.preprocessor.pdf_builder import PDFBuilder
        builder = PDFBuilder()
        builder.build_sample_knowledge()
        return True

    try:
        from src.crawler.medical_crawler import HealthcareCrawler, MEDICAL_SOURCES
        crawler = HealthcareCrawler(delay=2.0)
        results = crawler.crawl_all(MEDICAL_SOURCES)
        ok = sum(1 for r in results if r.get("status") == "success")
        logger.success(f"✅ Crawl xong: {ok}/{len(MEDICAL_SOURCES)} nguồn thành công")

        # Nếu crawl được ít hơn 30% → tạo thêm dữ liệu mẫu
        if ok < len(MEDICAL_SOURCES) * 0.3:
            logger.warning("⚠ Crawl ít thành công, tạo thêm dữ liệu mẫu...")
            from src.preprocessor.pdf_builder import PDFBuilder
            PDFBuilder().build_sample_knowledge()

        return True
    except Exception as e:
        logger.error(f"✗ Lỗi bước crawl: {e}")
        logger.info("  Tạo dữ liệu mẫu thay thế...")
        from src.preprocessor.pdf_builder import PDFBuilder
        PDFBuilder().build_sample_knowledge()
        return True


def step2_pdf(skip: bool = False):
    """Bước 2: Build PDF."""
    print_step(2, "BUILD PDF CHUẨN HÓA")

    if skip:
        logger.info("⏭ Bỏ qua bước PDF (--skip-pdf)")
        return True

    try:
        from src.preprocessor.pdf_builder import PDFBuilder
        builder = PDFBuilder()

        # Kiểm tra raw files
        txt_files = list((ROOT / "data/raw").glob("*.txt"))
        real_files = [f for f in txt_files if f.name != "crawl_metadata.json"]

        if not real_files:
            logger.warning("⚠ Không có file .txt, tạo dữ liệu mẫu...")
            builder.build_sample_knowledge()

        results = builder.build_all()
        ok = sum(1 for r in results if r["status"] == "success")
        logger.success(f"✅ Build PDF xong: {ok} file PDF tại data/pdfs/")
        return ok > 0
    except Exception as e:
        logger.error(f"✗ Lỗi bước PDF: {e}")
        return False


def step3_index(skip: bool = False):
    """Bước 3: Index vào Vector DB."""
    print_step(3, "INDEX VECTOR DATABASE")

    if skip:
        logger.info("⏭ Bỏ qua bước index (--skip-index)")
        return True

    try:
        from src.rag.indexer import VectorIndexer, load_all_pdfs, chunk_documents
        from pathlib import Path

        # Load PDFs
        docs = load_all_pdfs(Path("data/pdfs"))
        if not docs:
            logger.error("❌ Không có PDF để index!")
            return False

        # Chunk
        chunks = chunk_documents(docs)

        # Index
        indexer = VectorIndexer()
        indexer.index_chunks(chunks)

        stats = indexer.get_stats()
        logger.success(f"✅ Index xong: {stats['total_chunks']} chunks trong ChromaDB")

        # Test search
        logger.info("\n🔍 Test tìm kiếm mẫu:")
        hits = indexer.search("người tiểu đường ăn phở được không", top_k=2)
        for h in hits:
            logger.info(f"  [{h['similarity']:.2f}] {h['text'][:80]}...")

        return True
    except Exception as e:
        logger.error(f"✗ Lỗi bước index: {e}")
        import traceback; traceback.print_exc()
        return False


def step4_server(no_server: bool = False):
    """Bước 4: Khởi động API server."""
    print_step(4, "KHỞI ĐỘNG API SERVER")

    if no_server:
        logger.info("⏭ Bỏ qua khởi động server (--no-server)")
        logger.info("\n✅ Pipeline hoàn tất! Khởi động server thủ công:")
        logger.info("   uvicorn src.api.server:app --reload --port 8000")
        return

    logger.info("🌐 Khởi động FastAPI server...")
    logger.info("   URL:       http://localhost:8000")
    logger.info("   Swagger:   http://localhost:8000/docs")
    logger.info("   Frontend:  Mở file frontend/index.html trong trình duyệt")
    logger.info("\n   Nhấn Ctrl+C để dừng server\n")

    try:
        subprocess.run(
            [sys.executable, "-m", "uvicorn",
             "src.api.server:app",
             "--reload",
             "--host", os.getenv("API_HOST", "0.0.0.0"),
             "--port", os.getenv("API_PORT", "8000"),
             "--log-level", "info"],
            check=True,
            cwd=str(ROOT),
        )
    except KeyboardInterrupt:
        logger.info("\n👋 Server đã dừng")
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Lỗi server: {e}")


def main():
    parser = argparse.ArgumentParser(description="Healthcare RAG Pipeline")
    parser.add_argument("--skip-crawl",  action="store_true", help="Bỏ qua crawl")
    parser.add_argument("--skip-pdf",    action="store_true", help="Bỏ qua build PDF")
    parser.add_argument("--skip-index",  action="store_true", help="Bỏ qua index")
    parser.add_argument("--no-server",   action="store_true", help="Không start server")
    parser.add_argument("--demo-only",   action="store_true", help="Chỉ dùng dữ liệu mẫu")
    args = parser.parse_args()

    logger.info("🏥 HEALTHCARE RAG CHATBOT — PIPELINE SETUP")
    logger.info(f"   Thư mục: {ROOT}")

    # Kiểm tra .env
    has_key = check_env()
    if not has_key and not args.no_server:
        logger.warning("\n⚠ Lưu ý: Chatbot cần GEMINI_API_KEY để hoạt động!")
        logger.warning("  Điền key vào file .env trước khi test chatbot.\n")

    # Chạy các bước
    ok1 = step1_crawl(skip=args.skip_crawl, demo_only=args.demo_only)
    ok2 = step2_pdf(skip=args.skip_pdf) if ok1 else False
    ok3 = step3_index(skip=args.skip_index) if ok2 else False

    if ok3 or args.skip_index:
        step4_server(no_server=args.no_server)
    else:
        logger.error("\n❌ Pipeline thất bại ở bước index. Kiểm tra lỗi ở trên.")
        sys.exit(1)


if __name__ == "__main__":
    main()
