#!/usr/bin/env python3
"""
================================================================
START MOCK SERVER — Khởi động server ở chế độ demo
================================================================

Khi Gemini API vượt quota, có thể chạy server ở chế độ demo:
- Database được load bình thường (ChromaDB, embeddings)
- Trả lời là mock/demo (không gọi LLM)
- Ideal để test UI/UX hoặc demo sản phẩm

CÁCH CHẠY:
  python scripts/start_mock_server.py --port 8000
  
Sau đó:
  - API: http://localhost:8000
  - Docs: http://localhost:8000/docs
  - UI: http://localhost:8000
================================================================
"""

import os
import sys
import argparse
from pathlib import Path
from loguru import logger

# Setup paths
ROOT = Path(__file__).parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Set mock mode
os.environ["MOCK_LLM_MODE"] = "true"
os.environ["LLM_BACKEND"] = "mock"

# Import FastAPI app
from src.api.server import app
from src.rag.indexer import VectorIndexer

def main():
    parser = argparse.ArgumentParser(description="Start mock server (demo mode)")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code change")
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("🎮 MOCK SERVER (DEMO MODE)")
    logger.info("=" * 60)
    logger.warning("⚠️  LLM Mode: MOCK (không gọi Gemini API)")
    logger.warning("⚠️  Database: ChromaDB (ENABLED)")
    logger.warning("⚠️  Response: Demo/Mock")
    logger.info("=" * 60)
    
    # Check DB
    try:
        indexer = VectorIndexer()
        stats = indexer.get_stats()
        logger.success(f"✅ Vector DB: {stats['total_chunks']} chunks")
    except Exception as e:
        logger.warning(f"⚠️  Vector DB check failed: {e}")
    
    logger.info(f"\n🚀 Khởi động server...")
    logger.info(f"   URL: http://{args.host}:{args.port}")
    logger.info(f"   Docs: http://{args.host}:{args.port}/docs")
    logger.info(f"   Status: http://{args.host}:{args.port}/health")
    
    # Import uvicorn
    try:
        import uvicorn
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info",
        )
    except Exception as e:
        logger.error(f"❌ Lỗi khởi động: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
