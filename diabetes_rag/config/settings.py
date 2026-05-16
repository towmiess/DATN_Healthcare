"""Central config — loaded once, used everywhere."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ── LLM — Gemini ─────────────────────────────────────────────
GEMINI_API_KEY: str  = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str    = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ── Embeddings ───────────────────────────────────────────────
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

# ── Vector store ─────────────────────────────────────────────
CHROMA_DIR: Path     = BASE_DIR / os.getenv("CHROMA_PERSIST_DIR", "data/embeddings/chroma_db")
COLLECTION_NAME: str = "diabetes_knowledge_base"

# ── RAG tuning ───────────────────────────────────────────────
RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", 6))
FETCH_K: int         = 20
CHUNK_SIZE: int      = int(os.getenv("CHUNK_SIZE", 512))
CHUNK_OVERLAP: int   = int(os.getenv("CHUNK_OVERLAP", 80))
MAX_TOKENS: int      = 1500

# ── Data dirs ────────────────────────────────────────────────
RAW_DIR:       Path  = BASE_DIR / "data/raw"
PROCESSED_DIR: Path  = BASE_DIR / "data/processed"
