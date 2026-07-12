"""
src/rag/pipeline.py
────────────────────
RAG Pipeline — orchestrate Retrieve → Augment → Generate.

Kết hợp:
  - Retriever       (src/retrieval/retriever.py)
  - GeminiClient    (src/llm/gemini_client.py)
  - Prompt Builder  (src/prompts/templates.py)
  - RAGCache        (threading-safe, in-memory)
"""
from __future__ import annotations

import hashlib
import re
import threading
import time
from typing import Dict, List, Optional

from loguru import logger

from src.llm.gemini_client import GeminiClient, LLMAPIError
from src.ingestion.loader import parse_raw_metadata
from src.prompts.templates import (
    EMERGENCY_RESPONSE,
    SYSTEM_PROMPT,
    build_history_prompt,
    build_rag_prompt,
)
from src.retrieval.cache_manager import get_cache
from src.retrieval.retriever import Retriever, detect_intent, is_emergency
from src.utils.config import cfg
from src.utils.text_normalize import clean_llm_response
from src.vectordb.vector_store import VectorStore

# Re-export để server.py không phải thay import
__all__ = ["RAGPipeline", "LLMAPIError", "detect_intent"]


# ================================================================
# LONG-ANSWER DETECTION
# ================================================================
# Trước đây chỉ câu so sánh (is_comparison_query) mới được tăng max_tokens,
# còn lại fallback về None → cfg.llm.max_tokens (mặc định 1024), quá thấp
# cho câu trả lời dạng liệt kê nhiều mục/bước (ví dụ "phương pháp đĩa ăn"),
# gây cắt cụt giữa câu. Mở rộng heuristic để bắt thêm các câu hỏi dạng này.
_LONG_ANSWER_KEYWORDS = (
    "phương pháp", "các bước", "hướng dẫn", "quy trình", "nguyên tắc",
    "lưu ý", "tiêu chí", "danh sách", "liệt kê", "cách nào", "như thế nào",
    "bảng", "so sánh", "phân biệt", "khác nhau", "tác dụng phụ", "chống chỉ định",
)

# Từ khóa truy vấn thường cần nhiều tài liệu hơn để tránh thiếu ý.
_HIGH_RETRIEVAL_KEYWORDS = (
    "so sánh", "liệt kê", "lưu ý", "cách dùng", "cách sử dụng",
    "phân biệt", "khác nhau", "hướng dẫn", "quy trình", "nguy cơ",
)

# Token budget mặc định cho câu trả lời thường (trước đây là None → 1024)
_DEFAULT_MAX_TOKENS = 1800
# Token budget cho câu so sánh / câu cần liệt kê nhiều mục
_LONG_ANSWER_MAX_TOKENS = 2800


def _needs_long_answer(query: str) -> bool:
    """Heuristic: câu hỏi có khả năng cần trả lời dài (liệt kê, hướng dẫn nhiều bước)."""
    q = query.lower()
    return any(kw in q for kw in _LONG_ANSWER_KEYWORDS)


def _suggest_top_k(query: str, requested_top_k: Optional[int] = None) -> int:
    q = query.lower()
    base_top_k = requested_top_k or cfg.retrieval.top_k
    if any(keyword in q for keyword in _HIGH_RETRIEVAL_KEYWORDS):
        return max(base_top_k, 10)
    return max(base_top_k, 5)


def _items_fingerprint(items: Optional[List[Dict]]) -> str:
    """Hash ngắn cho tri thức/luật liên quan để cache không lẫn ngữ cảnh user."""
    normalized = []
    for item in items or []:
        text = (item.get("text") or item.get("content") or "").strip()
        if text:
            normalized.append(text)
    payload = "\n".join(sorted(normalized))
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:10] if payload else "none"


def _session_cache_query(route: str, query: str, memory_items: Optional[List[Dict]], response_rules: Optional[List[Dict]]) -> str:
    return (
        f"route={route}|q={' '.join(query.lower().split())}|"
        f"mem={_items_fingerprint(memory_items)}|rules={_items_fingerprint(response_rules)}"
    )


def _looks_contextual_query(query: str) -> bool:
    """Bỏ cache cho câu hỏi phụ thuộc lịch sử để tránh trả nhầm ở session khác."""
    q = query.lower().strip()
    contextual_markers = (
        "nó", "vậy", "cái đó", "điều đó", "thuốc đó", "bệnh đó",
        "tiếp", "còn gì", "như trên", "ở trên", "vừa rồi",
    )
    return len(q.split()) <= 8 and any(marker in q for marker in contextual_markers)


def _is_good_cache_candidate(response: str) -> bool:
    text = (response or "").strip()
    if len(text) < 80:
        return False
    bad_prefixes = (
        "❌",
        "⚠️",
        "Hiện tại mình chưa sinh được",
        "Không tìm thấy thông tin web phù hợp",
        "Mình đã thử chuyển qua các API key LLM khác",
    )
    return not any(text.startswith(prefix) for prefix in bad_prefixes)


# ================================================================
# RESPONSE CACHE
# ================================================================

class RAGCache:
    """Thread-safe in-memory cache cho response."""

    def __init__(self, max_size: int = None, ttl: int = None):
        self.max_size = max_size or cfg.cache.max_size
        self.ttl      = ttl or cfg.cache.ttl_s
        self._cache: Dict[str, dict] = {}
        self._ts:    Dict[str, float] = {}
        self._lock = threading.Lock()

    def make_key(self, query: str) -> str:
        return hashlib.md5(" ".join(query.lower().split()).encode()).hexdigest()

    def get(self, key: str) -> Optional[dict]:
        with self._lock:
            if key not in self._cache:
                return None
            if time.time() - self._ts[key] > self.ttl:
                del self._cache[key], self._ts[key]
                return None
            return self._cache[key]

    def set(self, key: str, value: dict) -> None:
        with self._lock:
            if len(self._cache) >= self.max_size:
                oldest = min(self._ts, key=self._ts.get)
                del self._cache[oldest], self._ts[oldest]
            self._cache[key] = value
            self._ts[key] = time.time()


# ================================================================
# RAG PIPELINE
# ================================================================

class RAGPipeline:
    """
    Orchestrates: Cache → Emergency → Retrieve → Generate.

    Dùng:
        pipeline = RAGPipeline()
        result = pipeline.answer("Tôi bị hạ đường huyết phải làm gì?")
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        gemini_client: Optional[GeminiClient] = None,
    ):
        store  = vector_store or VectorStore()
        self.store = store
        stats  = store.get_stats()
        if stats["total_chunks"] == 0:
            raise RuntimeError(
                "Vector Database trống!\n"
                "Chạy: python scripts/ingest.py"
            )

        self.retriever = Retriever(vector_store=store)
        if gemini_client is not None:
            self.llm = gemini_client
        else:
            self.llm = GeminiClient()
        self.cache     = RAGCache()

        logger.success(
            f"🚀 RAGPipeline sẵn sàng "
            f"({stats['total_chunks']} chunks | model={cfg.llm.model})"
        )

    def _best_response_rule_answer(
        self,
        query: str,
        response_rules: Optional[List[Dict]] = None,
        min_similarity: float = 0.68,
    ) -> Optional[str]:
        def _is_menu_query(value: str) -> bool:
            normalized = value.lower()
            return any(keyword in normalized for keyword in ("thực đơn", "dinh dưỡng", "ăn uống", "bữa ăn"))

        def _has_markdown_table(value: str) -> bool:
            return "|" in value and bool(re.search(r"^\s*\|?.+\|.+\n\s*\|?\s*:?-{2,}:?\s*\|", value, flags=re.M))

        def _strip_nested_instruction_prefix(value: str) -> str:
            compact = value.strip()
            if not re.match(r"^khi\s+", compact, flags=re.I):
                return compact
            answer_start = re.search(
                r"\b(chào bạn|dưới đây|để\s+|ví dụ|thực đơn dinh dưỡng|bữa sáng|sáng:)\b",
                compact,
                flags=re.I,
            )
            if answer_start and answer_start.start() >= 12:
                return compact[answer_start.start():].strip(" :-\n")
            return compact

        def _extract_direct_answer(rule_text: str) -> Optional[str]:
            text = rule_text.strip()
            if not text:
                return None
            # Chap nhan ca "thi tra loi:", "thi tra loi -" va "tra loi:". Nhieu
            # rule user day bang /nho hay bi thieu dau ":" nhung van la Q -> A.
            match = re.search(
                r"(?:trả lời|thì trả lời)\s*[:：-]\s*(.+)$",
                text,
                flags=re.I | re.S,
            )
            if match:
                answer = match.group(1).strip()
            else:
                qa_match = re.search(r"\?\s*\n+(.*)$", text, flags=re.I | re.S)
                if not qa_match:
                    return None
                answer = qa_match.group(1).strip()
            answer = _strip_nested_instruction_prefix(answer)
            answer = re.sub(r"^\s*nhớ rằng\s+", "", answer, flags=re.I).strip()
            return answer if len(answer) >= 20 else None

        rules = response_rules or []
        if not rules:
            return None

        # Với các câu hỏi thực đơn, ưu tiên rule đã được dạy bằng markdown table.
        # Nếu lấy rule text-phẳng đứng trên, UI chỉ render thành một cục chữ dài.
        best = rules[0]
        if _is_menu_query(query):
            table_rules = [
                rule for rule in rules
                if float(rule.get("similarity", 0) or 0) >= 0.60
                and _has_markdown_table(rule.get("text") or "")
            ]
            if table_rules:
                best = table_rules[0]

        candidate_rules = [best] + [rule for rule in rules if rule is not best]
        for rule in candidate_rules:
            similarity = float(rule.get("similarity", 0) or 0)
            if similarity < min_similarity:
                continue
            answer = _extract_direct_answer(rule.get("text") or "")
            if answer:
                return answer
        return None

    # ── Internal helpers ────────────────────────────────────────

    def _generate(self, query: str, chunks: List[Dict]) -> str:
        from src.retrieval.retriever import is_comparison_query
        prompt   = build_rag_prompt(query, chunks)
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        # Câu so sánh / câu cần liệt kê nhiều mục-bước → tăng token để tránh cắt cụt
        needs_long = is_comparison_query(query) or _needs_long_answer(query)
        max_tok    = _LONG_ANSWER_MAX_TOKENS if needs_long else _DEFAULT_MAX_TOKENS
        try:
            response = self.llm.generate(contents, system_prompt=SYSTEM_PROMPT, max_tokens=max_tok)
            text = self.llm.extract_text(response)
        except Exception as exc:
            logger.warning(f"[RAG] LLM lỗi khi generate '{query}': {exc}")
            return self._fallback_response_from_chunks(query, chunks, reason=str(exc))
        # Chuẩn hóa chính tả ("kì"→"kỳ", "type/týp"→"tuýp") + dọn citation còn sót
        return clean_llm_response(text)

    def _build_sources(self, chunks: List[Dict]) -> List[Dict]:
        sources_by_key: Dict[str, Dict] = {}
        ordered_chunks = sorted(chunks, key=lambda item: item.get("similarity", 0.0), reverse=True)
        for c in ordered_chunks:
            metadata = c.get("metadata", {})
            src = metadata.get("source", "unknown")
            source_url = metadata.get("source_url", "") or ""
            document_title = metadata.get("document_title", "") or metadata.get("title", "") or src
            if not source_url:
                document_id = metadata.get("document_id", "") or metadata.get("filename", "").rsplit(".", 1)[0]
                for base_dir in (cfg.paths.pdf_dir, cfg.paths.raw_dir):
                    if not document_id:
                        continue
                    candidates = list(base_dir.rglob(f"{document_id}.txt"))
                    for candidate in candidates:
                        raw_meta = parse_raw_metadata(document_id, candidate)
                        source_url = raw_meta.get("url", "") or source_url
                        if source_url:
                            break
                    if source_url:
                        break
            source_key = source_url or document_title or src
            current = {
                "source":     src,
                "title":      document_title,
                "url":        source_url,
                "filename":   metadata.get("filename", ""),
                "category":   metadata.get("category", ""),
                "similarity": c["similarity"],
            }
            previous = sources_by_key.get(source_key)
            if previous is None:
                sources_by_key[source_key] = current
                continue
            if not previous.get("url") and current.get("url"):
                sources_by_key[source_key] = current
            elif current["similarity"] > previous.get("similarity", 0.0):
                sources_by_key[source_key] = current

        sources = sorted(
            sources_by_key.values(),
            key=lambda item: (bool(item.get("url")), item.get("similarity", 0.0)),
            reverse=True,
        )
        return sources

    @staticmethod
    def _public_sources(items: List[Dict]) -> List[Dict]:
        hidden_categories = {"user_knowledge", "user_response_rule"}
        return [item for item in items if item.get("category") not in hidden_categories]

    @staticmethod
    def _fallback_response_from_chunks(query: str, chunks: List[Dict], reason: str = "") -> str:
        if not chunks:
            suffix = f" ({reason})" if reason else ""
            return (
                f"⚠️ Hiện tại mình chưa sinh được câu trả lời đầy đủ{suffix}. "
                "Bạn có thể thử lại sau ít phút."
            )

        lines = [
            "Mình chưa sinh được câu trả lời đầy đủ lúc này vì model đang bận hoặc quá tải.",
            "Dưới đây là vài đoạn liên quan để bạn xem nhanh:",
        ]
        for chunk in chunks[:3]:
            text = (chunk.get("text") or "").strip().replace("\n", " ")
            if len(text) > 360:
                text = text[:360].rsplit(" ", 1)[0] + "..."
            metadata = chunk.get("metadata", {})
            title = metadata.get("document_title") or metadata.get("title") or metadata.get("source") or "Tài liệu"
            lines.append(f"- {title}: {text}")
        lines.append("Nếu bạn muốn, hãy thử lại sau ít phút.")
        return "\n".join(lines)

    # ── Public API ──────────────────────────────────────────────

    def answer(
        self,
        query: str,
        top_k: int = None,
        patient_context: Optional[Dict] = None,
    ) -> Dict:
        """
        Single-turn answer.

        Returns:
            {query, response, sources, chunks_used, emergency?}
        """
        top_k = _suggest_top_k(query, top_k)
        intent = detect_intent(query)
        logger.info(f"❓ Query: '{query[:70]}' intent={intent}")

        # Câu so sánh/phân biệt cần nhiều chunk hơn để phủ đủ các khái niệm
        from src.retrieval.retriever import is_comparison_query
        if is_comparison_query(query):
            top_k = max(top_k, 10)
            logger.debug(f"  → câu so sánh, tăng top_k lên {top_k}")

        # 1. Emergency shortcut
        if is_emergency(query):
            return {
                "query": query, "response": EMERGENCY_RESPONSE,
                "sources": [], "chunks_used": 0, "emergency": True,
            }

        # 2. Cache check
        cache_key = self.cache.make_key(query)
        if not patient_context:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug("⚡ Cache hit")
                return cached

        # 3. Retrieve
        chunks = self.retriever.retrieve(query, top_k=top_k)

        # 4. Generate
        response = self._generate(query, chunks)

        result = {
            "query":       query,
            "response":    response,
            "sources":     self._build_sources(chunks),
            "chunks_used": len(chunks),
        }

        if not patient_context:
            self.cache.set(cache_key, result)

        logger.success(f"✅ Trả lời xong ({len(chunks)} chunks, {len(result['sources'])} nguồn)")
        return result

    def answer_with_knowledge(
        self,
        query: str,
        memory_items: Optional[List[Dict]] = None,
        response_rules: Optional[List[Dict]] = None,
        conversation_history: Optional[List[Dict]] = None,
        top_k: int = None,
        patient_context: Optional[Dict] = None,
    ) -> Dict:
        """
        Multi-turn cũ được đổi sang memory-based: nhận các tri thức người dùng đã lưu.

        Args:
            messages: List[{content|text: str}]
        """
        last_user = query
        if not last_user:
            return {"query": "", "response": "Không có câu hỏi.", "sources": [], "chunks_used": 0}

        top_k = _suggest_top_k(last_user, top_k)

        if is_emergency(last_user):
            return {
                "query": last_user, "response": EMERGENCY_RESPONSE,
                "sources": [], "chunks_used": 0, "emergency": True,
            }

        from src.retrieval.retriever import is_comparison_query
        is_cmp = is_comparison_query(last_user)
        if is_cmp:
            top_k = max(top_k, 10)
            logger.debug(f"  → câu so sánh (multi-turn), tăng top_k lên {top_k}")

        direct_rule = self._best_response_rule_answer(last_user, response_rules)
        if direct_rule:
            return {
                "query": last_user,
                "response": direct_rule,
                "sources": [],
                "chunks_used": 0,
                "from_cache": False,
                "route_type": "memory",
            }

        cache = get_cache()
        cache_lookup_key = None
        if not patient_context and not _looks_contextual_query(last_user):
            cache_lookup_key = _session_cache_query("document", last_user, memory_items, response_rules)
            cached = cache.get_llm_answer(cache_lookup_key)
            if cached:
                logger.debug(f"⚡ Session document cache HIT: {last_user[:60]}")
                return {
                    **cached,
                    "from_cache": True,
                    "route_type": cached.get("route_type", "document"),
                }

        chunks = self.retriever.retrieve(last_user, top_k=top_k)
        prompt = build_history_prompt(
            memory_items or [],
            last_user,
            chunks,
            conversation_history=conversation_history or [],
            response_rules=response_rules or [],
        )
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        needs_long = is_cmp or _needs_long_answer(last_user)
        max_tok    = _LONG_ANSWER_MAX_TOKENS if needs_long else _DEFAULT_MAX_TOKENS
        try:
            response_data = self.llm.generate(contents, system_prompt=SYSTEM_PROMPT, max_tokens=max_tok)
            response_text = clean_llm_response(self.llm.extract_text(response_data))
        except Exception as exc:
            logger.warning(f"[RAG] LLM lỗi khi answer_with_knowledge '{last_user}': {exc}")
            response_text = (
                "Mình đã thử chuyển qua các API key LLM khác nhưng model vẫn phản hồi quá chậm hoặc đang quá tải. "
                "Bạn vui lòng thử gửi lại câu hỏi sau ít phút; hệ thống sẽ ưu tiên dùng cache nếu câu này đã từng trả lời thành công."
            )

        result = {
            "query":       last_user,
            "response":    response_text,
            "sources":     self._public_sources(self._build_sources(chunks)),
            "chunks_used": len(chunks),
            "from_cache": False,
            "route_type": "document",
        }
        if cache_lookup_key and _is_good_cache_candidate(response_text):
            cache.set_llm_answer(cache_lookup_key, result, route_type="basic")
        return result


    async def answer_with_web_drug(
        self,
        query: str,
        top_k: int = None,
        memory_items: Optional[List[Dict]] = None,
        response_rules: Optional[List[Dict]] = None,
        conversation_history: Optional[List[Dict]] = None,
        patient_context: Optional[Dict] = None,
    ) -> Dict:
        """
        Answer drug questions using web search only.
        Non-drug questions fall back to the local document pipeline.
        """
        from src.retrieval.query_router import QueryRouter, RouteType
        from src.retrieval.web_search_client import search_drug_info_details

        top_k = top_k or cfg.retrieval.top_k
        decision = QueryRouter().route(query)

        if is_emergency(query):
            return {
                "query": query,
                "response": EMERGENCY_RESPONSE,
                "sources": [],
                "chunks_used": 0,
                "emergency": True,
                "route_type": "emergency",
            }

        if decision.route_type == RouteType.DRUG:
            direct_rule = self._best_response_rule_answer(query, response_rules)
            if direct_rule:
                return {
                    "query": query,
                    "response": direct_rule,
                    "sources": [],
                    "chunks_used": 0,
                    "route_type": "memory",
                }

            cache = get_cache()
            cache_lookup_key = None
            if not patient_context and not _looks_contextual_query(query):
                cache_lookup_key = _session_cache_query("drug", query, memory_items, response_rules)
                cached = cache.get_llm_answer(cache_lookup_key)
                if cached:
                    logger.debug(f"⚡ Session drug cache HIT: {query[:60]}")
                    return {
                        **cached,
                        "from_cache": True,
                        "route_type": cached.get("route_type", "drug"),
                    }

            drug_name = decision.drug_names[0] if decision.drug_names else query
            web_details = await search_drug_info_details(drug_name)
            web_context = web_details["text"] if web_details else None
            web_sources = web_details["sources"] if web_details else []
            if not web_context:
                web_context = "Không tìm thấy thông tin web phù hợp cho thuốc này."

            memory_block = "\n".join(
                f"[{i}] {item.get('text','')}"
                for i, item in enumerate(memory_items or [], 1)
                if item.get("text")
            ) or "Chưa có tri thức người dùng nào được lưu."
            rule_block = "\n".join(
                f"[{i}] {item.get('text','')}"
                for i, item in enumerate(response_rules or [], 1)
                if item.get("text")
            ) or "Chưa có luật trả lời nào được lưu."
            history_block = "\n".join(
                f"[{i}] {turn.get('role','')}: {turn.get('content') or turn.get('text','')}"
                for i, turn in enumerate(conversation_history or [], 1)
                if (turn.get("content") or turn.get("text"))
            ) or "Chưa có lịch sử hội thoại trước đó."

            prompt = f"""\
## THÔNG TIN THUỐC TỪ WEB

{web_context}

## LUẬT TRẢ LỜI NGƯỜI DÙNG ĐÃ DẠY

{rule_block}

## TRI THỨC NGƯỜI DÙNG ĐÃ LƯU

{memory_block}

## LỊCH SỬ HỘI THOẠI GẦN ĐÂY

{history_block}

---

## CÂU HỎI

{query}

---

## YÊU CẦU TRẢ LỜI

1. Ưu tiên LUẬT TRẢ LỜI NGƯỜI DÙNG ĐÃ DẠY nếu có liên quan, sau đó đến tri thức người dùng, rồi đến web.
2. Chỉ dựa trên thông tin ở trên và các tri thức/nguyên tắc được cung cấp.
3. Trả lời ngắn gọn, rõ ràng, dễ hiểu.
4. Nếu dữ liệu chưa đủ chắc chắn thì nói rõ và khuyên hỏi bác sĩ/dược sĩ.
5. Không bịa đặt thêm thông tin.
6. Không được chép nguyên văn LUẬT TRẢ LỜI NGƯỜI DÙNG ĐÃ DẠY vào câu trả lời; chỉ dùng luật đó như hướng dẫn về cấu trúc/cách trình bày.
7. Nếu trình bày bằng bảng markdown, bắt buộc có dòng phân cách "|---|---|" ngay dưới header; không dùng tab để tách cột và không xuống dòng trong một ô bảng.
"""
            contents = [{"role": "user", "parts": [{"text": prompt}]}]
            max_tok = _LONG_ANSWER_MAX_TOKENS if _needs_long_answer(query) else _DEFAULT_MAX_TOKENS
            try:
                response_data = self.llm.generate(contents, system_prompt=SYSTEM_PROMPT, max_tokens=max_tok)
                response_text = clean_llm_response(self.llm.extract_text(response_data))
            except Exception as exc:
                logger.warning(f"[RAG] LLM lỗi khi answer_with_web_drug '{query}': {exc}")
                response_text = (
                    "Mình đã thử chuyển qua các API key LLM khác nhưng model vẫn phản hồi quá chậm hoặc đang quá tải. "
                    "Bạn vui lòng thử lại sau ít phút; mình sẽ không hiển thị fallback tài liệu thô để tránh câu trả lời bị lỗi định dạng."
                )
            result = {
                "query": query,
                "response": response_text,
                "sources": self._public_sources([
                    {
                        "source": item.get("title") or item.get("url") or "Web search",
                        "title": item.get("title") or item.get("url") or "Web search",
                        "url": item.get("url", ""),
                        "category": "drug",
                        "similarity": 1.0,
                    }
                    for item in (web_sources[:5] if web_sources else [{"title": "Web search", "url": ""}])
                ]),
                "chunks_used": 0,
                "route_type": "drug",
                "from_cache": False,
            }
            if cache_lookup_key and _is_good_cache_candidate(response_text):
                cache.set_llm_answer(cache_lookup_key, result, route_type="drug")
            return result

        result = self.answer(query, top_k=top_k, patient_context=patient_context)
        result["route_type"] = "document"
        return result

    # ── Expose for compatibility ────────────────────────────────

    def retrieve(self, query: str, top_k: int = None) -> List[Dict]:
        """Expose retrieve() cho server.py /search endpoint."""
        return self.retriever.retrieve(query, top_k=top_k or cfg.retrieval.top_k)

    def generate(self, query: str, chunks: List[Dict]) -> str:
        """Expose generate() cho server.py /chat/stream endpoint."""
        return self._generate(query, chunks)
    
    async def hybrid_answer(
        self,
        query: str,
        session_id: str = "default",
        top_k: int = None,
        skip_llm_cache: bool = False,
    ) -> Dict:
        """
        Hybrid retrieval: Qdrant + OpenFDA (tra cứu thuốc) + web cache.
        PubMed đã bị loại bỏ khỏi pipeline (không dùng nghiên cứu khoa học).
        Dùng cho luồng tra cứu thuốc khi cần web.
        """
        import asyncio
        import time
        from src.retrieval.query_router import QueryRouter, RouteType
        from src.retrieval.cache_manager import get_cache
        from src.retrieval.openfda_client import lookup_drugs_for_rag, format_fda_context
        from src.retrieval.realtime_fetcher import fetch_realtime_context
        from src.retrieval.retriever import is_emergency, is_comparison_query

        t0     = time.time()
        top_k  = top_k or cfg.retrieval.top_k
        cache  = get_cache()
        router = QueryRouter()

        # ── 1. Route ──────────────────────────────────────────
        decision = router.route(query)
        logger.info(f"[HybridRAG] {decision.to_log_str()} | '{query[:50]}'")

        # ── 2. Khẩn cấp → shortcut ────────────────────────────
        if is_emergency(query) or decision.is_emergency:
            from src.prompts.templates import EMERGENCY_RESPONSE
            return {
                "query": query, "response": EMERGENCY_RESPONSE,
                "sources": [], "chunks_used": 0, "emergency": True,
                "route_type": "emergency", "response_time_ms": 0,
                "from_cache": False,
            }

        # ── 3. LLM cache check ────────────────────────────────
        if not skip_llm_cache:
            cached = cache.get_llm_answer(query)
            if cached:
                logger.debug("⚡ LLM cache HIT")
                return {**cached, "from_cache": True,
                        "route_type": decision.route_type.value}

        # ── 4. Fetch song song ────────────────────────────────
        async def _qdrant():
            return self.retriever.retrieve(query, top_k=top_k)

        async def _user_knowledge():
            try:
                return self.store.search_user_knowledge(query, top_k=6)
            except Exception as exc:
                logger.warning(f"[HybridRAG] search_user_knowledge lỗi: {exc}")
                return []

        async def _response_rules():
            try:
                return self.store.search_user_response_rule(query, top_k=6)
            except Exception as exc:
                logger.warning(f"[HybridRAG] search_user_response_rule lỗi: {exc}")
                return []

        async def _noop_dict():
            return {}

        async def _noop_none():
            return None

        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    _qdrant(),
                    _user_knowledge(),
                    _response_rules(),
                    (lookup_drugs_for_rag(decision.drug_names)
                     if decision.use_openfda and decision.drug_names else _noop_dict()),
                    (fetch_realtime_context(query)
                     if decision.use_realtime else _noop_none()),
                    return_exceptions=True,
                ),
                timeout=12,   # lưới an toàn: không để 1 nguồn ngoài "treo" cả response
            )
        except asyncio.TimeoutError:
            logger.warning("[HybridRAG] timeout khi fetch song song → fallback Qdrant-only")
            results = [await _qdrant(), [], [], {}, None]

        chunks         = results[0] if not isinstance(results[0], Exception) else []
        memory_items   = results[1] if not isinstance(results[1], Exception) else []
        response_rules = results[2] if not isinstance(results[2], Exception) else []
        fda_results    = results[3] if not isinstance(results[3], Exception) else {}
        web_content    = results[4] if not isinstance(results[4], Exception) else None

        # Chỉ giữ tri thức người dùng có độ liên quan đủ cao (tránh nhiễu
        # khi câu hỏi hoàn toàn không liên quan tới bất kỳ mẩu nào đã lưu)
        _MIN_MEMORY_SIMILARITY = 0.45
        memory_items = [m for m in (memory_items or [])
                         if m.get("similarity", 0) >= _MIN_MEMORY_SIMILARITY]

        # Cache FDA mới fetch
        for drug, info in (fda_results or {}).items():
            if info.get("label") and not cache.get_fda(drug):
                try:
                    cache.set_fda(drug, info["label"].to_dict())
                except Exception:
                    pass

        # ── 5. Build context ──────────────────────────────────
        parts = []
        if response_rules:
            parts.append("=== Luat tra loi nguoi dung da luu ===")
            for i, r in enumerate(response_rules, 1):
                parts.append(f"[{i}] {r.get('text','')}")
        if memory_items:
            parts.append("=== Tri thuc nguoi dung da luu ===")
            for i, m in enumerate(memory_items, 1):
                parts.append(f"[{i}] {m.get('text','')}")
        if chunks:
            parts.append("=== Tai lieu da index ===")
            for i, c in enumerate(chunks, 1):
                m = c["metadata"]
                parts.append(
                    f"[{i}. {m.get('source','?')} | {m.get('category','')}]\n"
                    f"{c.get('text','')[:600]}"
                )
        if fda_results:
            fb = format_fda_context(fda_results)
            if fb:
                parts.append("\n" + fb)
        if web_content:
            parts.append(f"\n=== Thong tin cap nhat (CDC) ===\n{web_content[:1500]}")

        context = "\n\n".join(parts)

        # ── 6. Gọi Gemini ─────────────────────────────────────
        drug_note = (
            f"\nCâu hỏi về thuốc: {', '.join(decision.drug_names)}. "
            f"Ưu tiên thông tin OpenFDA, khuyên tham khảo bác sĩ/dược sĩ.\n"
            if decision.drug_names else ""
        )
        full_prompt = (
            f"Dựa trên thông tin tham khảo dưới đây, trả lời câu hỏi.\n"
            f"Luôn ưu tiên LUẬT TRẢ LỜI NGƯỜI DÙNG ĐÃ LƯU nếu liên quan trực tiếp, rồi mới đến tri thức người dùng và tài liệu.{drug_note}\n\n"
            f"--- THÔNG TIN THAM KHẢO ---\n{context}\n"
            f"--- KẾT THÚC ---\n\n"
            f"Câu hỏi: {query}"
        )
        from src.prompts.templates import SYSTEM_PROMPT
        contents  = [{"role": "user", "parts": [{"text": full_prompt}]}]
        needs_long = is_comparison_query(query) or _needs_long_answer(query)
        max_tok   = _LONG_ANSWER_MAX_TOKENS if needs_long else _DEFAULT_MAX_TOKENS

        try:
            raw      = self.llm.generate(contents, system_prompt=SYSTEM_PROMPT, max_tokens=max_tok)
            response = clean_llm_response(self.llm.extract_text(raw))
        except Exception as e:
            logger.warning(f"[HybridRAG] LLM lỗi: {e} → fallback Gemini")
            try:
                raw      = self.llm.generate(contents, system_prompt=SYSTEM_PROMPT, max_tokens=max_tok)
                response = clean_llm_response(self.llm.extract_text(raw))
            except Exception as e2:
                response = f"❌ Lỗi LLM: {e2}"

        # ── 7. Build sources ──────────────────────────────────
        sources = self._build_sources(chunks)
        for m in (memory_items or []):
            sources.append({"source": "Tri thuc nguoi dung da luu",
                            "category": "user_knowledge",
                            "similarity": m.get("similarity", 1.0)})
        for drug in (fda_results or {}):
            sources.append({"source": f"OpenFDA:{drug}",
                            "category": "medication", "similarity": 1.0})
        if web_content:
            sources.append({"source": "CDC (realtime)",
                            "category": "realtime", "similarity": 1.0})

        result = {
            "query":            query,
            "response":         response,
            "sources":          sources,
            "chunks_used":      len(chunks),
            "route_type":       decision.route_type.value,
            "from_cache":       False,
            "response_time_ms": int((time.time() - t0) * 1000),
        }

        # ── 8. Cache LLM answer ───────────────────────────────
        cache.set_llm_answer(query, result, route_type=decision.route_type.value)
        logger.success(
            f"✅ hybrid_answer done | route={decision.route_type.value} "
            f"qdrant={len(chunks)} "
            f"fda={len(fda_results or {})} | {result['response_time_ms']}ms"
        )
        return result
