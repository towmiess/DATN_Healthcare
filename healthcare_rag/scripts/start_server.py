#!/usr/bin/env python3
"""
================================================================
START SERVER — Khởi động server với LLM backend selection
================================================================

CÁCH CHẠY:

  1. Chế độ Gemini (bình thường):
     python scripts/start_server.py --llm gemini

  2. Chế độ Ollama (local):
     python scripts/start_server.py --llm ollama

  3. Chế độ Mock/Demo (không LLM):
     python scripts/start_server.py --llm mock

  4. Tự động chọn backend khả dụng:
     python scripts/start_server.py  (mặc định: auto)

OPTIONS:
  --port PORT          Server port (default 8000)
  --host HOST          Server host (default 0.0.0.0)
  --llm {gemini|ollama|mock|auto}  LLM backend (default auto)
  --reload             Auto-reload on code change
  --no-server-mode     Chỉ kiểm tra config, không start server
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

def configure_llm_backend(backend: str):
    """Cấu hình backend LLM với auto-fallback."""
    from src.rag.llm_manager import LLMManager
    manager = LLMManager()
    available = manager.get_available_backends()
    
    # If user requested a specific backend that's not available, try to fallback
    if backend != "auto" and backend not in available:
        logger.warning(f"⚠️ Requested backend '{backend}' not available")
        logger.info(f"   Available: {available}")
        
        # Auto-fallback logic
        if "gemini" in available:
            logger.warning(f"   Fallback: Using Gemini")
            backend = "gemini"
        elif "mock" in available:
            logger.warning(f"   Fallback: Using Mock mode")
            backend = "mock"
        else:
            backend = "mock"
    
    elif backend == "auto":
        # Auto-detect best available
        if "gemini" in available:
            logger.success("✅ Gemini API available")
            backend = "gemini"
        elif "ollama" in available:
            logger.warning("⚠️ Gemini not available, using Ollama")
            backend = "ollama"
        else:
            logger.warning("⚠️ Using Mock mode")
            backend = "mock"
        
        logger.info(f"🎯 Auto-selected backend: {backend}")
    
    # Cấu hình environment
    os.environ["LLM_BACKEND"] = backend
    
    if backend == "mock":
        os.environ["MOCK_LLM_MODE"] = "true"
        logger.warning("🎭 Running in MOCK mode (demo only)")
    elif backend == "ollama":
        os.environ["USE_OLLAMA"] = "true"
        logger.info("🦙 Using Ollama as LLM backend")
    elif backend == "gemini":
        logger.info("🔷 Using Gemini as LLM backend")
    
    return backend

def check_backend_availability(backend: str):
    """Kiểm tra backend khả dụng."""
    from src.rag.llm_manager import LLMManager
    manager = LLMManager()
    
    logger.info("\n" + "=" * 60)
    logger.info("🔍 SYSTEM STATUS")
    logger.info("=" * 60)
    
    # Check Gemini
    if manager.is_gemini_available():
        logger.success("✅ Gemini API: READY")
    else:
        logger.warning("⚠️ Gemini API: NOT CONFIGURED (key missing or invalid)")
    
    # Check Ollama
    if manager.is_ollama_available():
        logger.success(f"✅ Ollama: RUNNING ({manager.ollama_url})")
    else:
        logger.warning(f"⚠️ Ollama: NOT RUNNING (expected at {manager.ollama_url})")
    
    # Check Vector DB
    try:
        from src.rag.indexer import VectorIndexer
        indexer = VectorIndexer()
        stats = indexer.get_stats()
        logger.success(f"✅ ChromaDB: {stats['total_chunks']} chunks loaded")
    except Exception as e:
        logger.error(f"❌ ChromaDB: ERROR - {e}")
    
    # Show available backends
    available = manager.get_available_backends()
    logger.info(f"\n📋 Available backends: {available}")
    
    # Warn if not available
    if backend not in available and backend != "auto":
        logger.error(f"❌ Backend '{backend}' is NOT available!")
        logger.info(f"   Available: {available}")
        return False
    
    logger.info("=" * 60 + "\n")
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Start Healthcare RAG Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("SERVER_PORT", 8000)),
        help="Server port (default 8000)"
    )
    parser.add_argument(
        "--host",
        default=os.getenv("SERVER_HOST", "0.0.0.0"),
        help="Server host (default 0.0.0.0)"
    )
    parser.add_argument(
        "--llm",
        choices=["gemini", "ollama", "mock", "auto"],
        default="auto",
        help="LLM backend (default auto)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Auto-reload on code change"
    )
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Only check config, don't start server"
    )
    
    args = parser.parse_args()
    
    # Configure LLM
    backend = configure_llm_backend(args.llm)
    
    # Check availability (informational only)
    check_backend_availability(backend)
    
    # Start server
    if args.no_server:
        logger.info("✅ Config check passed")
        sys.exit(0)
    
    logger.info(f"🚀 Khởi động server...")
    logger.info(f"   URL: http://{args.host}:{args.port}")
    logger.info(f"   Docs: http://{args.host}:{args.port}/docs")
    logger.info(f"   Backend: {backend}")
    logger.info(f"   Reload: {args.reload}")
    
    # Import FastAPI app
    from src.api.server import app
    
    try:
        import uvicorn
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info",
        )
    except KeyboardInterrupt:
        logger.info("\n✋ Server stopped")
    except Exception as e:
        logger.error(f"❌ Lỗi: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
