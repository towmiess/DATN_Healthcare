"""
Đọc config.yaml và cho phép override bằng biến môi trường.

Dùng:
    from src.utils.config import cfg
    url = cfg.qdrant.url
    model = cfg.llm.model
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

try:
    import yaml
    _YAML_OK = True
except ImportError:
    _YAML_OK = False


# ── Root của project ────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent.parent
_CONFIG_FILE = _ROOT / "config.yaml"


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not _YAML_OK or not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _env(key: str, default: Any, cast=str) -> Any:
    val = os.getenv(key, "")
    return cast(val) if val else default


# ── Simple namespace wrapper ─────────────────────────────────────
class _NS:
    def __init__(self, d: Dict[str, Any]):
        for k, v in d.items():
            if isinstance(v, dict):
                setattr(self, k, _NS(v))
            else:
                setattr(self, k, v)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class Config:
    """Singleton — đọc config.yaml + env override."""

    _instance: Optional["Config"] = None

    def __new__(cls) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        raw = _load_yaml(_CONFIG_FILE)

        # ── qdrant ──────────────────────────────────────────────
        q = raw.get("qdrant", {})
        self.qdrant = _NS({
            "url":        _env("QDRANT_URL",        q.get("url", "http://localhost:6333")),
            "collection": _env("QDRANT_COLLECTION",  q.get("collection", "healthcare_diabetes")),
            "api_key":    _env("QDRANT_API_KEY",     q.get("api_key", "")),
        })

        # ── embedding ────────────────────────────────────────────
        e = raw.get("embedding", {})
        self.embedding = _NS({
            "model":       _env("EMBEDDING_MODEL", e.get("model", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")),
            "vector_size": int(e.get("vector_size", 384)),
        })

        # ── chunking ─────────────────────────────────────────────
        ck = raw.get("chunking", {})
        self.chunking = _NS({
            "chunk_size":      int(_env("CHUNK_SIZE",    ck.get("chunk_size", 400),    int)),
            "chunk_overlap":   int(_env("CHUNK_OVERLAP", ck.get("chunk_overlap", 80), int)),
            "min_chunk_chars": int(ck.get("min_chunk_chars", 50)),
        })

        # ── llm ──────────────────────────────────────────────────
        l = raw.get("llm", {})
        fb_raw = _env("GEMINI_FALLBACK_MODELS", "")
        fb_from_env = [m.strip() for m in fb_raw.split(",") if m.strip()] if fb_raw else []
        fb = fb_from_env or l.get("fallback_models", ["gemini-2.5-flash"])
        self.llm = _NS({
            "model":            _env("LLM_MODEL",           l.get("model", "gemini-2.0-flash-lite")),
            "max_tokens":       int(_env("MAX_TOKENS",       l.get("max_tokens", 2048),  int)),
            "temperature":      float(_env("LLM_TEMPERATURE", l.get("temperature", 0.1), float)),
            "timeout_s":        int(_env("LLM_TIMEOUT",      l.get("timeout_s", 60),     int)),
            "max_retries":      int(_env("LLM_MAX_RETRIES",  l.get("max_retries", 2),    int)),
            "retry_base_delay": float(_env("LLM_RETRY_BASE_DELAY", l.get("retry_base_delay", 1.0), float)),
            "retry_max_delay":  float(_env("LLM_RETRY_MAX_DELAY",  l.get("retry_max_delay", 8.0),  float)),
            "thinking_budget":  int(_env("GEMINI_THINKING_BUDGET", l.get("thinking_budget", 0), int)),
            "api_base":         _env("GEMINI_API_BASE", l.get("api_base", "https://generativelanguage.googleapis.com/v1beta")),
            "fallback_models":  fb,
        })

        # ── retrieval ────────────────────────────────────────────
        r = raw.get("retrieval", {})
        self.retrieval = _NS({
            "top_k":                    int(_env("RAG_TOP_K", r.get("top_k", 4), int)),
            "candidate_multiplier":     int(r.get("candidate_multiplier", 4)),
            "min_similarity_general":   float(r.get("min_similarity_general", 0.24)),
            "min_similarity_specific":  float(r.get("min_similarity_specific", 0.28)),
            "rerank_semantic_weight":   float(r.get("rerank_semantic_weight", 0.85)),
            "rerank_priority_weight":   float(r.get("rerank_priority_weight", 0.15)),
        })

        # ── cache ────────────────────────────────────────────────
        c = raw.get("cache", {})
        self.cache = _NS({
            "max_size": int(c.get("max_size", 200)),
            "ttl_s":    int(c.get("ttl_s", 3600)),
        })

        # ── user knowledge ───────────────────────────────────────
        uk = raw.get("user_knowledge", {})
        enabled_raw = _env("USER_KNOWLEDGE_ENABLED", "")
        self.user_knowledge = _NS({
            "enabled":          (enabled_raw.lower() not in {"0", "false", "no", ""}) if enabled_raw else bool(uk.get("enabled", False)),
            "min_chars":        int(uk.get("min_chars", 40)),
            "rule_top_k":       int(uk.get("rule_top_k", 3)),
            "rule_min_similarity": float(uk.get("rule_min_similarity", 0.18)),
        })

        # ── paths ────────────────────────────────────────────────
        p = raw.get("paths", {})
        self.paths = _NS({
            "pdf_dir": Path(_env("PDF_DIR", p.get("pdf_dir", "data/pdfs"))),
            "raw_dir": Path(p.get("raw_dir", "data/raw")),
            "logs_dir": Path(p.get("logs_dir", "logs")),
        })


# Singleton export
cfg = Config()