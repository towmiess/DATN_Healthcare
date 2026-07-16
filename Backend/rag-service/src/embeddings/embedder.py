"""
src/embeddings/embedder.py
──────────────────────────
Singleton wrapper quanh SentenceTransformer.

Fix Windows: tạo thư mục HuggingFace cache nếu chưa có.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import List, Optional

from loguru import logger

from src.utils.config import cfg

_MODEL_NAME = cfg.embedding.model


def _ensure_hf_cache() -> None:
    """
    Đảm bảo thư mục HuggingFace cache tồn tại.
    Trên Windows, ~/.cache/huggingface đôi khi không được tạo tự động.
    """
    # Ưu tiên: biến môi trường HF_HOME hoặc HUGGINGFACE_HUB_CACHE
    hf_home = os.environ.get("HF_HOME") or os.environ.get("HUGGINGFACE_HUB_CACHE")
    if not hf_home:
        # Mặc định: ~/.cache/huggingface
        hf_home = str(Path.home() / ".cache" / "huggingface")

    cache_path = Path(hf_home)
    if not cache_path.exists():
        logger.info(f"📁 Tạo thư mục HuggingFace cache: {cache_path}")
        cache_path.mkdir(parents=True, exist_ok=True)

    # Set env để transformers / huggingface_hub dùng đúng path
    os.environ.setdefault("HF_HOME", str(cache_path))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(cache_path / "hub"))
    Path(os.environ["HUGGINGFACE_HUB_CACHE"]).mkdir(parents=True, exist_ok=True)


class Embedder:
    """Singleton SentenceTransformer wrapper."""

    _instance: Optional["Embedder"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "Embedder":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        # Fix Windows path trước khi import
        _ensure_hf_cache()

        from sentence_transformers import SentenceTransformer

        logger.info(f"🧠 Tải embedding model: {_MODEL_NAME}")
        try:
            self._model = SentenceTransformer(_MODEL_NAME)
        except Exception as exc:
            # Nếu model chưa có trên máy, log rõ cách tải
            logger.error(
                f"❌ Không tải được model '{_MODEL_NAME}': {exc}\n"
                f"   → Thử chạy trước:\n"
                f"     python -c \"from sentence_transformers import SentenceTransformer; "
                f"SentenceTransformer('{_MODEL_NAME}')\"\n"
                f"   hoặc đặt HF_HOME trong .env trỏ tới thư mục cache hợp lệ."
            )
            raise

        logger.success(
            f"✅ Embedding model sẵn sàng "
            f"(model={_MODEL_NAME}, dim={cfg.embedding.vector_size})"
        )

    def encode(self, texts: List[str]) -> List[List[float]]:
        """Encode list of texts → list of float vectors."""
        vectors = self._model.encode(texts, show_progress_bar=False)
        return vectors.tolist()

    @property
    def vector_size(self) -> int:
        return cfg.embedding.vector_size

    @property
    def model_name(self) -> str:
        return _MODEL_NAME


def get_embedder() -> Embedder:
    """Factory — trả về singleton Embedder."""
    return Embedder()
