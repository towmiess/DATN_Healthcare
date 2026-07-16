"""
cache_manager.py
================
Cache layer tập trung cho toàn bộ RAG system.

TTL strategy theo loại dữ liệu:
  ┌─────────────────────────┬──────────┬──────────────────────────┐
  │ Loại                    │ TTL      │ Lý do                    │
  ├─────────────────────────┼──────────┼──────────────────────────┤
  │ Câu trả lời LLM (basic) │ 7200s    │ câu hỏi thường gặp       │
  │ Câu trả lời LLM (drug)  │ 7200s    │ thuốc ít thay đổi        │
  │ Câu trả lời LLM (realtime)│ 1800s  │ thông tin mới            │
  │ OpenFDA drug info       │ 604800s  │ nhãn thuốc rất ổn định   │
  │ Real-time web fetch     │ 86400s   │ nội dung web 24h         │
  │ Health check API        │ 30s      │ cần fresh                │
  └─────────────────────────┴──────────┴──────────────────────────┘

Tự động fallback sang in-memory cache nếu Redis không khả dụng.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

log = logging.getLogger(__name__)

# ── TTL constants (giây) ──────────────────────────────────────
TTL = {
    "llm_basic":    14400,    # 4 giờ
    "llm_drug":     21600,    # 6 giờ
    "llm_realtime": 3600,     # 1 giờ
    "llm_hybrid":   14400,    # 4 giờ
    "llm_emergency": 300,     # 5 phút (muốn người dùng luôn có thông tin mới nhất)
    "openfda":      604800,   # 7 ngày
    "realtime_web": 86400,    # 24 giờ
    "api_health":   30,       # 30 giây
}

# Cache key prefixes
PREFIX = {
    "llm":      "rag:llm:",
    "openfda":  "rag:fda:",
    "web":      "rag:web:",
    "health":   "rag:health:",
}


# ══════════════════════════════════════════════════════════════
# In-memory fallback cache
# ══════════════════════════════════════════════════════════════

@dataclass
class _MemEntry:
    value: str
    expires_at: float

    def is_alive(self) -> bool:
        return time.time() < self.expires_at

    def ttl_remaining(self) -> int:
        return max(0, int(self.expires_at - time.time()))


class _MemCache:
    """Thread-safe in-memory cache với LRU eviction đơn giản."""

    def __init__(self, max_size: int = 500):
        self._store: dict[str, _MemEntry] = {}
        self._max = max_size

    def get(self, key: str) -> Optional[str]:
        entry = self._store.get(key)
        if entry and entry.is_alive():
            return entry.value
        if entry:
            del self._store[key]  # expired
        return None

    def set(self, key: str, value: str, ttl: int):
        # Evict oldest nếu đầy
        if len(self._store) >= self._max:
            oldest = min(self._store.items(), key=lambda x: x[1].expires_at)
            del self._store[oldest[0]]
        self._store[key] = _MemEntry(value=value, expires_at=time.time() + ttl)

    def delete(self, key: str):
        self._store.pop(key, None)

    def delete_pattern(self, pattern: str):
        """Xóa tất cả key chứa pattern (thay thế đơn giản cho Redis SCAN)."""
        to_delete = [k for k in self._store if pattern.replace("*", "") in k]
        for k in to_delete:
            del self._store[k]

    def stats(self) -> dict:
        alive = sum(1 for e in self._store.values() if e.is_alive())
        return {"total": len(self._store), "alive": alive, "max": self._max}


# ══════════════════════════════════════════════════════════════
# Redis wrapper
# ══════════════════════════════════════════════════════════════

class _RedisCache:
    def __init__(self, host: str, port: int, db: int = 0):
        import redis
        self._r = redis.Redis(
            host=host, port=port, db=db,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=True,
        )
        self._r.ping()  # Test connection

    def get(self, key: str) -> Optional[str]:
        return self._r.get(key)

    def set(self, key: str, value: str, ttl: int):
        self._r.setex(key, ttl, value)

    def delete(self, key: str):
        self._r.delete(key)

    def delete_pattern(self, pattern: str):
        """Xóa tất cả key khớp pattern (ví dụ: 'rag:fda:*')."""
        cursor = 0
        while True:
            cursor, keys = self._r.scan(cursor, match=pattern, count=100)
            if keys:
                self._r.delete(*keys)
            if cursor == 0:
                break

    def stats(self) -> dict:
        info = self._r.info("memory")
        keyspace = self._r.info("keyspace")
        return {
            "backend": "redis",
            "used_memory_mb": info["used_memory"] / 1024 / 1024,
            "keyspace": keyspace,
        }


# ══════════════════════════════════════════════════════════════
# CacheManager — unified interface
# ══════════════════════════════════════════════════════════════

class CacheManager:
    """
    Interface duy nhất cho toàn bộ cache trong RAG system.
    Tự động fallback sang MemCache nếu Redis không khả dụng.

    Dùng:
        cache = CacheManager()

        # LLM answer cache
        cache.set_llm_answer("metformin liều dùng", answer, route_type="drug")
        answer = cache.get_llm_answer("metformin liều dùng")

        # OpenFDA cache
        cache.set_fda(drug_name, fda_data)
        data = cache.get_fda("metformin")

        # Real-time web cache
        cache.set_web(url, content)
        content = cache.get_web(url)
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
    ):
        self._backend_name = "redis"
        try:
            self._backend = _RedisCache(redis_host, redis_port)
            log.info("✅ Cache backend: Redis")
        except Exception as e:
            log.warning(f"⚠  Redis không khả dụng ({e}) → dùng in-memory cache")
            self._backend = _MemCache(max_size=500)
            self._backend_name = "memory"

    @property
    def using_redis(self) -> bool:
        return self._backend_name == "redis"

    # ── Key builders ──────────────────────────────────────────

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.md5(text.lower().strip().encode()).hexdigest()[:12]

    def _llm_key(self, query: str) -> str:
        return PREFIX["llm"] + self._hash(query)

    def _fda_key(self, drug_name: str) -> str:
        return PREFIX["openfda"] + drug_name.lower().replace(" ", "_")

    def _web_key(self, url: str) -> str:
        return PREFIX["web"] + self._hash(url)

    def _health_key(self) -> str:
        return PREFIX["health"] + "status"

    # ── LLM answer cache ──────────────────────────────────────

    def get_llm_answer(self, query: str) -> Optional[dict]:
        """Trả về cached answer dict hoặc None."""
        raw = self._backend.get(self._llm_key(query))
        if raw:
            try:
                data = json.loads(raw)
                log.debug(f"Cache HIT llm: {query[:40]}")
                return data
            except json.JSONDecodeError:
                pass
        return None

    def set_llm_answer(self, query: str, answer_data: dict, route_type: str = "hybrid"):
        """
        Lưu answer kèm metadata.
        answer_data: {"response": str, "sources": list, "chunks_used": int, ...}
        """
        ttl_key = f"llm_{route_type}"
        ttl = TTL.get(ttl_key, TTL["llm_hybrid"])

        payload = {
            **answer_data,
            "_cached": True,
            "_cached_at": int(time.time()),
            "_route": route_type,
        }
        self._backend.set(self._llm_key(query), json.dumps(payload, ensure_ascii=False), ttl)
        log.debug(f"Cache SET llm ({ttl}s): {query[:40]}")

    # ── OpenFDA cache ─────────────────────────────────────────

    def get_fda(self, drug_name: str) -> Optional[dict]:
        raw = self._backend.get(self._fda_key(drug_name))
        if raw:
            try:
                log.debug(f"Cache HIT fda: {drug_name}")
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
        return None

    def set_fda(self, drug_name: str, fda_data: dict):
        self._backend.set(
            self._fda_key(drug_name),
            json.dumps(fda_data, ensure_ascii=False),
            TTL["openfda"],
        )

    # ── Real-time web cache ───────────────────────────────────

    def get_web(self, url: str) -> Optional[str]:
        result = self._backend.get(self._web_key(url))
        if result:
            log.debug(f"Cache HIT web: {url[:50]}")
        return result

    def set_web(self, url: str, content: str):
        self._backend.set(self._web_key(url), content, TTL["realtime_web"])

    # ── API Health cache ──────────────────────────────────────

    def get_health(self) -> Optional[dict]:
        raw = self._backend.get(self._health_key())
        return json.loads(raw) if raw else None

    def set_health(self, health_data: dict):
        self._backend.set(
            self._health_key(),
            json.dumps(health_data),
            TTL["api_health"],
        )

    # ── Admin operations ──────────────────────────────────────

    def invalidate_llm(self, query: str):
        """Xóa cache cho 1 query cụ thể."""
        self._backend.delete(self._llm_key(query))

    def invalidate_all_llm(self):
        """Xóa toàn bộ LLM answer cache — dùng sau rebuild index."""
        self._backend.delete_pattern(PREFIX["llm"] + "*")
        log.info("🗑  Đã xóa toàn bộ LLM cache")

    def invalidate_fda(self, drug_name: str = None):
        """Xóa FDA cache cho 1 thuốc hoặc tất cả."""
        if drug_name:
            self._backend.delete(self._fda_key(drug_name))
        else:
            self._backend.delete_pattern(PREFIX["openfda"] + "*")
            log.info("🗑  Đã xóa toàn bộ FDA cache")

    def stats(self) -> dict:
        return {
            "backend": self._backend_name,
            **self._backend.stats(),
        }


# ── Singleton ──────────────────────────────────────────────────
_cache_instance: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """Trả về singleton CacheManager. Gọi 1 lần khi FastAPI startup."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheManager(
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", 6379)),
        )
    return _cache_instance


# ══════════════════════════════════════════════════════════════
# CLI test
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    cache = get_cache()
    print(f"\nBackend: {cache._backend_name}")
    print(f"Stats: {cache.stats()}")

    # Test LLM cache
    test_query = "Metformin uống lúc nào tốt nhất?"
    test_answer = {
        "response": "Metformin nên uống trong hoặc sau bữa ăn để giảm tác dụng phụ tiêu hóa.",
        "sources": ["vinmec", "cdc_basics"],
        "chunks_used": 3,
        "response_time_ms": 1200,
    }

    cache.set_llm_answer(test_query, test_answer, route_type="drug")
    retrieved = cache.get_llm_answer(test_query)

    print(f"\n✅ LLM cache test:")
    print(f"   SET: {test_query}")
    print(f"   GET: {retrieved['response'][:60]}…")
    print(f"   _cached: {retrieved.get('_cached')}")

    # Test FDA cache
    cache.set_fda("metformin", {"drug_name": "Metformin", "indications": "Type 2 DM"})
    fda = cache.get_fda("metformin")
    print(f"\n✅ FDA cache test: {fda}")

    # Test cache miss
    miss = cache.get_llm_answer("câu hỏi chưa có trong cache")
    print(f"\n✅ Cache miss test: {miss}")  # → None

    print(f"\nStats: {cache.stats()}")
