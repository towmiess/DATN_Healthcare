"""
src/rag/session.py
───────────────────
Redis session store với in-memory fallback.

Cấu hình:
  REDIS_URL      = redis://localhost:6379
  SESSION_TTL_S  = 3600  (1 giờ)
  SESSION_MAX_TURNS = 20 (giữ 20 lượt hội thoại gần nhất)
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from loguru import logger


_REDIS_URL      = os.getenv("REDIS_URL", "redis://localhost:6379")
_SESSION_TTL    = int(os.getenv("SESSION_TTL_S", 3600))
_MAX_TURNS      = int(os.getenv("SESSION_MAX_TURNS", 20))
_CHAT_HISTORY_TTL = int(os.getenv("CHAT_HISTORY_TTL_S", 60 * 60 * 24 * 30))


class SessionStore:
    """
    Lưu lịch sử hội thoại theo session_id.

    - Redis nếu khả dụng (persistent, đa process)
    - Dict trong bộ nhớ nếu Redis không có (dev mode)
    """

    def __init__(self):
        self._redis    = None
        self._mem: Dict[str, List[Dict]] = {}
        self._chat_state_mem: Dict[str, Dict] = {}
        self.redis_enabled = False
        self._try_redis()

    def _try_redis(self) -> None:
        try:
            import redis as redis_lib
            client = redis_lib.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=2)
            client.ping()
            self._redis = client
            self.redis_enabled = True
            logger.success(f"✅ Redis session store: {_REDIS_URL}")
        except Exception as exc:
            logger.warning(f"⚠ Redis không khả dụng ({exc}) → dùng in-memory")

    # ── Key helper ─────────────────────────────────────────────

    @staticmethod
    def _key(session_id: str) -> str:
        return f"rag:session:{session_id}"

    @staticmethod
    def _chat_state_key(user_key: str) -> str:
        return f"rag:chat_history:{user_key}"

    # ── Public API ─────────────────────────────────────────────

    def get_history(self, session_id: str) -> List[Dict]:
        """Trả về lịch sử hội thoại (list of {role, content})."""
        if self._redis:
            try:
                raw = self._redis.get(self._key(session_id))
                return json.loads(raw) if raw else []
            except Exception as exc:
                logger.error(f"Redis get lỗi: {exc}")
        return list(self._mem.get(session_id, []))

    def append(self, session_id: str, role: str, content: str) -> None:
        """Thêm một lượt vào lịch sử."""
        history = self.get_history(session_id)
        history.append({"role": role, "content": content})

        # Giữ tối đa MAX_TURNS lượt
        if len(history) > _MAX_TURNS:
            history = history[-_MAX_TURNS:]

        self._save(session_id, history)

    def clear(self, session_id: str) -> None:
        """Xóa toàn bộ lịch sử của session."""
        if self._redis:
            try:
                self._redis.delete(self._key(session_id))
                return
            except Exception as exc:
                logger.error(f"Redis delete lỗi: {exc}")
        self._mem.pop(session_id, None)

    def get_chat_state(self, user_key: str) -> Dict:
        """Trả về danh sách session chat đã lưu theo user_key."""
        if self._redis:
            try:
                raw = self._redis.get(self._chat_state_key(user_key))
                return json.loads(raw) if raw else {"activeSessionId": "", "sessions": []}
            except Exception as exc:
                logger.error(f"Redis get chat history lỗi: {exc}")
        return dict(self._chat_state_mem.get(user_key, {"activeSessionId": "", "sessions": []}))

    def save_chat_state(self, user_key: str, state: Dict) -> None:
        """Lưu snapshot lịch sử chat theo user_key để đồng bộ giữa trình duyệt."""
        safe_state = {
            "activeSessionId": state.get("activeSessionId", ""),
            "sessions": state.get("sessions", []),
        }
        if self._redis:
            try:
                self._redis.setex(
                    self._chat_state_key(user_key),
                    _CHAT_HISTORY_TTL,
                    json.dumps(safe_state, ensure_ascii=False),
                )
                return
            except Exception as exc:
                logger.error(f"Redis save chat history lỗi: {exc}")
        self._chat_state_mem[user_key] = safe_state

    def delete_chat_session_snapshot(self, user_key: str, session_id: str) -> Dict:
        """Xóa một session khỏi danh sách lịch sử theo user_key."""
        state = self.get_chat_state(user_key)
        sessions = [
            session
            for session in state.get("sessions", [])
            if session.get("sessionId") != session_id
        ]
        if state.get("activeSessionId") == session_id:
            state["activeSessionId"] = sessions[0].get("sessionId", "") if sessions else ""
        state["sessions"] = sessions
        self.save_chat_state(user_key, state)
        return state

    # ── Private ────────────────────────────────────────────────

    def _save(self, session_id: str, history: List[Dict]) -> None:
        if self._redis:
            try:
                self._redis.setex(self._key(session_id), _SESSION_TTL, json.dumps(history))
                return
            except Exception as exc:
                logger.error(f"Redis setex lỗi: {exc}")
        self._mem[session_id] = history
