#!/usr/bin/env python3
"""
================================================================
FIX CHROMADB CORRUPTION — Tự động repair ChromaDB
================================================================

Khi ChromaDB bị corrupt (TypeError: object of type 'int' has no len()),
script này sẽ:
1. Detect corruption
2. Xóa database cũ
3. Rebuild từ PDF
4. Verify kết quả

CÁCH CHẠY:
  python scripts/repair_chromadb.py
================================================================
"""

import os
import sys
import shutil
from pathlib import Path
from loguru import logger

# Setup paths
ROOT = Path(__file__).parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

def check_chromadb_health():
    """Kiểm tra ChromaDB có bị corrupt không."""
    logger.info("🔍 Checking ChromaDB health...")
    
    try:
        from src.rag.indexer import VectorIndexer
        indexer = VectorIndexer()
        stats = indexer.get_stats()
        logger.success(f"✅ ChromaDB OK: {stats['total_chunks']} chunks")
        return True
    except TypeError as e:
        if "has no len()" in str(e):
            logger.error("❌ ChromaDB CORRUPT: SQLite format mismatch")
            return False
    except Exception as e:
        logger.error(f"❌ ChromaDB ERROR: {e}")
        return False

def backup_chromadb():
    """Backup database cũ."""
    db_dir = Path("data/chroma_db")
    backup_dir = Path("data/chroma_db_backup")
    
    if db_dir.exists():
        logger.info(f"📦 Backing up old database to {backup_dir}...")
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(db_dir, backup_dir)
        logger.success("✅ Backup created")
        return True
    return False

def clean_chromadb():
    """Xóa database corrupt."""
    db_dir = Path("data/chroma_db")
    
    if db_dir.exists():
        logger.warning(f"🗑️  Removing corrupt database...")
        try:
            shutil.rmtree(db_dir)
            db_dir.mkdir(parents=True, exist_ok=True)
            logger.success("✅ Database cleared")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to remove database: {e}")
            return False
    return True

def rebuild_chromadb():
    """Rebuild database từ PDF."""
    logger.info("🔨 Rebuilding database from PDFs...")
    
    try:
        from src.rag.indexer import load_all_pdfs, chunk_documents, VectorIndexer
        
        # Load PDFs
        logger.info("📄 Loading PDFs...")
        documents = load_all_pdfs(Path("data/pdfs"))
        if not documents:
            logger.error("❌ No documents found!")
            return False
        
        # Chunk
        logger.info("📦 Creating chunks...")
        chunks = chunk_documents(documents)
        
        # Index
        logger.info("🔗 Indexing into ChromaDB...")
        indexer = VectorIndexer()
        indexer.index_chunks(chunks)
        
        logger.success("✅ Database rebuilt successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Rebuild failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_chromadb():
    """Verify database khả dụng."""
    logger.info("✔️  Verifying database...")
    
    try:
        from src.rag.indexer import VectorIndexer
        indexer = VectorIndexer()
        stats = indexer.get_stats()
        
        if stats['total_chunks'] > 0:
            logger.success(f"✅ Verification passed: {stats['total_chunks']} chunks")
            logger.info(f"   Categories: {stats['categories']}")
            return True
        else:
            logger.error("❌ Database is empty!")
            return False
            
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        return False

def main():
    logger.info("=" * 60)
    logger.info("🔧 ChromaDB Repair Tool")
    logger.info("=" * 60)
    
    # Step 1: Check current state
    if check_chromadb_health():
        logger.success("\n✅ ChromaDB is healthy - no repair needed!")
        sys.exit(0)
    
    # Step 2: Backup
    backup_chromadb()
    
    # Step 3: Clean
    if not clean_chromadb():
        logger.error("\n❌ Failed to clean database")
        sys.exit(1)
    
    # Step 4: Rebuild
    if not rebuild_chromadb():
        logger.error("\n❌ Failed to rebuild database")
        logger.info("💡 Possible fixes:")
        logger.info("   1. Check data/pdfs/ has PDF files")
        logger.info("   2. Ensure dependencies: pip install -r requirements.txt")
        logger.info("   3. Try: pip install --upgrade chromadb")
        sys.exit(1)
    
    # Step 5: Verify
    if not verify_chromadb():
        logger.error("\n❌ Verification failed")
        sys.exit(1)
    
    logger.info("\n" + "=" * 60)
    logger.success("✅ ChromaDB repair completed successfully!")
    logger.info("=" * 60)
    logger.info("\n📖 Next steps:")
    logger.info("   python scripts/start_server.py --llm mock")
    logger.info("   or")
    logger.info("   python scripts/start_server.py --llm ollama")

if __name__ == "__main__":
    main()
