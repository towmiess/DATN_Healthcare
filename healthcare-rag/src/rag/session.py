"""
Session Store — Lưu lịch sử hội thoại bằng Redis.

Fallback sang in-memory nếu Redis không có.
"""

import json
import os
from typing import List, Dict, Optional
from loguru import logger

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class SessionStore:
    """
    Lưu lịch sử chat theo session_id.
    - Redis: persistent, tồn tại qua restart
    - Memory: fallback khi Redis không khả dụng
    """

    def __init__(self):
        self.redis_enabled = False
        self._client = None
        self._memory: Dict[str, List[Dict]] = {}
        self.ttl = int(os.getenv("REDIS_TTL", 3600))

        if REDIS_AVAILABLE:
            host = os.getenv("REDIS_HOST", "")
            port = int(os.getenv("REDIS_PORT", 6379))
            if host:
                try:
                    self._client = redis.Redis(
                        host=host,
                        port=port,
                        db=0,
                        decode_responses=True,
                        socket_connect_timeout=3,
                    )
                    self._client.ping()
                    self.redis_enabled = True
                    logger.success(f"✅ Redis session store: {host}:{port}")
                except Exception as e:
                    logger.warning(f"⚠ Redis không khả dụng ({e}), dùng in-memory")

        if not self.redis_enabled:
            logger.info("📝 Session store: in-memory (không persistent)")

    def _key(self, session_id: str) -> str:
        return f"rag:session:{session_id}"

    def get_history(self, session_id: str) -> List[Dict]:
        if self.redis_enabled:
            try:
                data = self._client.get(self._key(session_id))
                return json.loads(data) if data else []
            except Exception:
                pass
        return self._memory.get(session_id, [])

    def append(self, session_id: str, role: str, content: str) -> None:
        history = self.get_history(session_id)
        history.append({"role": role, "content": content})

        # Giới hạn lịch sử 20 lượt (tránh prompt quá dài)
        if len(history) > 40:
            history = history[-40:]

        if self.redis_enabled:
            try:
                self._client.setex(
                    self._key(session_id),
                    self.ttl,
                    json.dumps(history, ensure_ascii=False),
                )
                return
            except Exception:
                pass
        self._memory[session_id] = history

    def clear(self, session_id: str) -> None:
        if self.redis_enabled:
            try:
                self._client.delete(self._key(session_id))
            except Exception:
                pass
        self._memory.pop(session_id, None)
