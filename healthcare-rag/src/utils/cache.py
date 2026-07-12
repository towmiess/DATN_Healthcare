"""
src/utils/cache.py
───────────────────
Thread-safe in-memory LRU cache với TTL.

Dùng ở bất kỳ đâu cần cache kết quả:
    from src.utils.cache import TTLCache

    cache = TTLCache(max_size=200, ttl=3600)
    cache.set("key", {"result": "..."})
    val = cache.get("key")   # None nếu hết TTL
"""
from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from typing import Any, Optional

from src.utils.config import cfg


class TTLCache:
    """
    LRU cache thread-safe với Time-To-Live.

    - Khi đầy → evict entry cũ nhất (LRU)
    - Khi get() → kiểm tra TTL, xóa nếu hết hạn
    - Key có thể là bất kỳ string nào
    """

    def __init__(self, max_size: int = None, ttl: int = None):
        self.max_size = max_size or cfg.cache.max_size
        self.ttl      = ttl      or cfg.cache.ttl_s

        self._data: OrderedDict[str, Any]   = OrderedDict()
        self._ts:   dict[str, float]        = {}
        self._lock  = threading.Lock()

    # ── Write ─────────────────────────────────────────────────

    def set(self, key: str, value: Any) -> None:
        """Lưu value theo key. Evict LRU nếu đầy."""
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            else:
                if len(self._data) >= self.max_size:
                    oldest_key, _ = self._data.popitem(last=False)
                    self._ts.pop(oldest_key, None)
            self._data[key] = value
            self._ts[key]   = time.monotonic()

    # ── Read ──────────────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        """
        Trả về value nếu còn TTL, ngược lại trả None và xóa.
        Cũng cập nhật vị trí LRU khi hit.
        """
        with self._lock:
            if key not in self._data:
                return None
            age = time.monotonic() - self._ts[key]
            if age > self.ttl:
                del self._data[key], self._ts[key]
                return None
            self._data.move_to_end(key)   # mark as recently used
            return self._data[key]

    # ── Delete ────────────────────────────────────────────────

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)
            self._ts.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._ts.clear()

    # ── Housekeeping ──────────────────────────────────────────

    def evict_expired(self) -> int:
        """Chủ động xóa tất cả entry hết TTL. Trả về số entry đã xóa."""
        now  = time.monotonic()
        dead = [k for k, t in self._ts.items() if now - t > self.ttl]
        with self._lock:
            for k in dead:
                self._data.pop(k, None)
                self._ts.pop(k, None)
        return len(dead)

    # ── Stats ─────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self._data)

    def stats(self) -> dict:
        now = time.monotonic()
        with self._lock:
            alive   = sum(1 for t in self._ts.values() if now - t <= self.ttl)
            expired = len(self._ts) - alive
        return {
            "size":     len(self._data),
            "alive":    alive,
            "expired":  expired,
            "max_size": self.max_size,
            "ttl_s":    self.ttl,
        }

    # ── Convenience: hash-based key ───────────────────────────

    @staticmethod
    def make_key(text: str) -> str:
        """Tạo key ngắn gọn từ text tuỳ độ dài."""
        normalized = " ".join(text.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()
