"""
src/api/server.py
──────────────────
FastAPI backend — dùng các module mới (refactored).

Endpoints:
  GET  /health
  GET  /stats
  POST /chat
  POST /chat/session
  POST /chat/stream
  DELETE /chat/session/{id}
  GET  /search
  POST /admin/upload
  GET  /admin/documents
  DELETE /admin/documents/{id}
  POST /admin/rebuild-index
"""
from __future__ import annotations

import asyncio
import base64
import hmac
import json
import os
import re
import time
import uuid
from hashlib import sha256
from pathlib import Path
from typing import List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

load_dotenv()

from src.ingestion.loader import extract_text_from_pdf
from src.llm.gemini_client import LLMAPIError
from src.rag.pipeline import RAGPipeline, detect_intent
from src.rag.session import SessionStore
from src.vectordb.vector_store import VectorStore

# ── App ────────────────────────────────────────────────────────
app = FastAPI(
    title="🏥 Healthcare RAG API v2",
    description="Chatbot tư vấn tiểu đường — RAG + Gemini + Qdrant + Redis",
    version="2.0.0",
)
ADMIN_KEY  = os.getenv("ADMIN_SECRET_KEY",  "healthcare-admin-dev")
DOCTOR_KEY = os.getenv("DOCTOR_SECRET_KEY", "healthcare-doctor-dev")
GATEWAY_INTERNAL_SECRET = os.getenv("GATEWAY_INTERNAL_SECRET", "change-me-in-production")
ALLOW_DIRECT_ACCESS = os.getenv("RAG_ALLOW_DIRECT_ACCESS", "false").lower() in {"1", "true", "yes"}


def _is_valid_gateway_signature(encoded_payload: str, signature: Optional[str]) -> bool:
    if not signature:
        return False

    expected = base64.b64encode(
        hmac.new(
            GATEWAY_INTERNAL_SECRET.encode("utf-8"),
            encoded_payload.encode("utf-8"),
            sha256,
        ).digest()
    ).decode("utf-8")

    return hmac.compare_digest(expected, signature)


@app.middleware("http")
async def gateway_only_middleware(request: Request, call_next):
    """
    Require every request to be signed by api-gateway.
    This prevents clients from bypassing port 8000 and calling rag-service directly.
    """
    if not ALLOW_DIRECT_ACCESS:
        encoded_payload = request.headers.get("X-User-Context")
        signature = request.headers.get("X-User-Context-Signature")

        if encoded_payload is None or not _is_valid_gateway_signature(encoded_payload, signature):
            return JSONResponse(
                status_code=403,
                content={"message": "Rag-service must be accessed through api-gateway"},
            )

    return await call_next(request)

# Singletons
rag: Optional[RAGPipeline] = None
store: Optional[VectorStore] = None
session_store: Optional[SessionStore] = None


@app.on_event("startup")
async def startup():
    global rag, store, session_store
    logger.info("🚀 Khởi động Healthcare RAG Server v2...")
    try:
        session_store = SessionStore()
        store = VectorStore()
        stats = store.get_stats()
        if stats["total_chunks"] == 0:
            logger.warning("⚠ Vector DB trống! Chạy: python scripts/ingest.py")
        else:
            rag = RAGPipeline(vector_store=store)
            logger.success(f"✅ Server sẵn sàng! ({stats['total_chunks']} chunks)")
    except Exception as exc:
        logger.error(f"❌ Lỗi khởi động: {exc}")


def _require_key(token: Optional[str], expected: str, action: str):
    if token != expected:
        raise HTTPException(403, f"Không có quyền: {action}")


def _safe_name(name: str) -> str:
    import re
    return re.sub(r"[^\w\-.]", "_", name)[:80]


def _should_remember_knowledge(message: str) -> bool:
    text = message.strip().lower()
    pattern = r"^(?:/nho|nhớ rằng|ghi nhớ rằng|lưu ý rằng|thông tin của tôi là|tri thức mới)\s*:?\s+"
    return bool(re.match(pattern, text))


def _strip_knowledge_prefix(message: str) -> str:
    text = message.strip()
    pattern = r"^(?:/nho|nhớ rằng|ghi nhớ rằng|lưu ý rằng|thông tin của tôi là|tri thức mới)\s*:?\s+"
    return re.sub(pattern, "", text, flags=re.IGNORECASE).strip()


def _looks_like_response_rule(message: str) -> bool:
    text = message.strip().lower()
    patterns = (
        r"\bthì trả lời\b",
        r"\bhãy trả lời\b",
        r"\btrả lời:\s*",
        r"\bkhi hỏi\b",
        r"\bkhi người dùng hỏi\b",
        r"\bnếu hỏi\b",
        r"\bnếu người dùng hỏi\b",
        r"\bluôn trả lời\b",
        r"\bphải trả lời\b",
        r"\btrả lời như sau\b",
        r"\bcâu trả lời.*(?:cần|phải|nên)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _canonicalize_teaching_text(message: str) -> Tuple[str, bool]:
    """Chuan hoa noi dung nguoi dung day thanh knowledge hoac response rule.

    Dang hay gap: "/nho khi lap thuc don ... De xay dung ...".
    Neu luu nguyen van, vector search co the xem day la tri thuc thuong va LLM
    khong uu tien dung. Chuyen thanh "khi ... thi tra loi: <answer>" de pipeline
    co the lay thang dap an da duoc day khi cau hoi khop ngu canh.
    """
    raw = message.strip()
    compact = re.sub(r"[ \t]+", " ", raw)
    single_line = re.sub(r"\s+", " ", raw)
    if not raw:
        return "", False

    if re.search(r"(?:trả lời|thì trả lời)\s*[:：-]\s*", raw, flags=re.I):
        return raw, True

    question_match = re.match(r"^(.{8,180}\?)\s*\n+(.{20,})", raw, flags=re.I | re.S)
    if question_match:
        trigger = re.sub(r"\s+", " ", question_match.group(1)).strip()
        answer = question_match.group(2).strip()
        return f"{trigger} thì trả lời:\n{answer}", True

    if not re.match(r"^khi\s+", single_line, flags=re.I):
        return raw, _looks_like_response_rule(single_line)

    answer_start_patterns = (
        r"\bchào bạn\b",
        r"\bdưới đây\b",
        r"\bđể\s+",
        r"\bví dụ\b",
        r"\bbữa\s+(?:sáng|trưa|tối|ăn)\b",
        r"\blưu ý\b",
    )
    answer_start = None
    for pattern in answer_start_patterns:
        match = re.search(pattern, single_line, flags=re.I)
        if match and match.start() >= 20:
            answer_start = match.start() if answer_start is None else min(answer_start, match.start())

    if answer_start is not None:
        trigger = single_line[:answer_start].strip(" :-,.;")
        answer = single_line[answer_start:].strip()
        if len(trigger) >= 10 and len(answer) >= 40:
            return f"{trigger} thì trả lời: {answer}", True

    # Neu nguoi dung bat dau bang "khi ..." trong che do ghi nho, uu tien luu nhu
    # rule de khong bi tron vao block tri thuc thuong.
    return raw, len(raw) >= 40


def _filter_user_knowledge_items(items: List[dict]) -> List[dict]:
    """Không đưa các luật hướng dẫn trả lời bị lưu nhầm vào block tri thức."""
    clean_items: List[dict] = []
    for item in items or []:
        text = (item.get("text") or item.get("content") or "").strip()
        if text and _looks_like_response_rule(text):
            continue
        clean_items.append(item)
    return clean_items


def _normalize_sources(items) -> List["SourceInfo"]:
    sources: List[SourceInfo] = []
    for item in items or []:
        if isinstance(item, dict):
            sources.append(SourceInfo(**item))
        else:
            sources.append(SourceInfo(source=str(item)))
    return sources


# ================================================================
# SCHEMAS
# ================================================================

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=8000)
    top_k: int = Field(default=4, ge=1, le=10)
    patient_context: Optional[dict] = None


class SessionChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(..., min_length=3, max_length=8000)
    top_k: int = Field(default=4, ge=1, le=10)
    remember_knowledge: bool = Field(default=False)


class ChatHistoryState(BaseModel):
    activeSessionId: str = ""
    sessions: List[dict] = Field(default_factory=list)


class SourceInfo(BaseModel):
    source: str
    title: str = ""
    url: str = ""
    category: str = ""
    similarity: float = 0.0


class ChatResponse(BaseModel):
    query: str
    response: str
    sources: List[SourceInfo]
    chunks_used: int
    response_time_ms: int
    intent: str = ""


class SessionChatResponse(BaseModel):
    session_id: str
    query: str
    response: str
    sources: List[SourceInfo]
    chunks_used: int
    response_time_ms: int
    route_type: str = ""


class ChatV2Request(BaseModel):
    message: str = Field(..., min_length=2, max_length=8000)
    session_id: Optional[str] = None
    top_k: int = Field(default=6, ge=1, le=12)
    skip_llm_cache: bool = Field(default=False)


class ChatV2Response(BaseModel):
    query: str
    response: str
    sources: List[SourceInfo]
    chunks_used: int
    route_type: str = ""
    from_cache: bool = False
    response_time_ms: int


# ================================================================
# HEALTH & STATS
# ================================================================

@app.get("/health", tags=["System"])
async def health():
    s = store.get_stats() if store else {}
    return {
        "status": "ok",
        "rag_ready": rag is not None,
        "total_chunks": s.get("total_chunks", 0),
        "session_store": "redis" if (session_store and session_store.redis_enabled) else "memory",
    }


@app.get("/stats", tags=["System"])
async def stats():
    if not store:
        raise HTTPException(503, "Store chưa sẵn sàng")
    return store.get_stats()


# ================================================================
# CHAT — Single Turn
# ================================================================

@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(req: ChatRequest):
    if not rag:
        raise HTTPException(503, "RAG pipeline chưa sẵn sàng. Chạy ingest.py trước.")
    t0 = time.monotonic()
    try:
        result = rag.answer(req.query, top_k=req.top_k, patient_context=req.patient_context)
    except LLMAPIError as exc:
        raise HTTPException(502, f"LLM error: {exc}")
    except Exception as exc:
        logger.error(f"Chat error: {exc}")
        raise HTTPException(500, str(exc))

    return ChatResponse(
        query=result["query"],
        response=result["response"],
        sources=[SourceInfo(**s) for s in result.get("sources", [])],
        chunks_used=result.get("chunks_used", 0),
        response_time_ms=int((time.monotonic() - t0) * 1000),
        intent=detect_intent(req.query),
    )


# ================================================================
# CHAT — Multi-turn Session
# ================================================================

@app.post("/chat/session", response_model=SessionChatResponse, tags=["Chat"])
async def chat_session(req: SessionChatRequest):
    if not rag:
        raise HTTPException(503, "RAG pipeline chưa sẵn sàng")

    session_id = req.session_id or str(uuid.uuid4())
    from src.retrieval.query_router import QueryRouter, RouteType

    # Tri thức user là GLOBAL — không filter theo session_id.
    # Lọc thêm các "luật trả lời" lỡ bị lưu nhầm vào user_knowledge để không
    # bị LLM chép nguyên văn hướng dẫn vào câu trả lời.
    memory_items = _filter_user_knowledge_items(store.search_user_knowledge(req.message, top_k=6)) if store else []
    response_rules = store.search_user_response_rule(req.message, top_k=6) if store else []
    conversation_history = session_store.get_history(session_id)[-8:] if session_store else []
    remember_knowledge = req.remember_knowledge or _should_remember_knowledge(req.message)
    knowledge_text = req.message
    if remember_knowledge:
        knowledge_text = _strip_knowledge_prefix(knowledge_text)

    stored_knowledge_text, knowledge_is_response_rule = _canonicalize_teaching_text(knowledge_text)
    teaching_mode = remember_knowledge
    if teaching_mode:
        if not knowledge_text:
            raise HTTPException(400, "Thiếu nội dung cần ghi nhớ")
        stored_as_rule = False
        if store:
            if knowledge_is_response_rule:
                store.upsert_user_response_rule(stored_knowledge_text, source="user", added_by="user")
                stored_as_rule = True
            else:
                store.upsert_user_knowledge(knowledge_text, source="user", added_by="user")
        stored_text = "Đã ghi nhớ luật trả lời" if stored_as_rule else "Đã ghi nhớ tri thức"
        if session_store:
            session_store.append(session_id, "user", req.message)
            session_store.append(session_id, "assistant", f"{stored_text}: {knowledge_text}")
        return SessionChatResponse(
            session_id=session_id,
            query=req.message,
            response=f"{stored_text}: {knowledge_text}",
            sources=[],
            chunks_used=0,
            response_time_ms=0,
            route_type="memory",
        )

    t0 = time.monotonic()
    try:
        decision = QueryRouter().route(req.message)
        if decision.route_type == RouteType.EMERGENCY:
            result = await rag.answer_with_web_drug(
                req.message,
                top_k=req.top_k,
                memory_items=memory_items,
                response_rules=response_rules,
                conversation_history=conversation_history,
            )
            route_type = "emergency"
        elif decision.route_type == RouteType.DRUG:
            result = await rag.answer_with_web_drug(
                req.message,
                top_k=req.top_k,
                memory_items=memory_items,
                response_rules=response_rules,
                conversation_history=conversation_history,
            )
            route_type = "drug"
        else:
            result = rag.answer_with_knowledge(
                req.message,
                memory_items=memory_items,
                response_rules=response_rules,
                conversation_history=conversation_history,
                top_k=req.top_k,
            )
            route_type = "document"
    except LLMAPIError as exc:
        raise HTTPException(502, f"LLM error: {exc}")
    except Exception as exc:
        logger.error(f"Session chat error: {exc}")
        raise HTTPException(500, str(exc))

    # Lưu tri thức VĨNH VIỄN — không gắn session, persist qua mọi session
    if store and remember_knowledge and knowledge_text:
        if knowledge_is_response_rule:
            store.upsert_user_response_rule(stored_knowledge_text, source="user", added_by="user")
        else:
            store.upsert_user_knowledge(knowledge_text, source="user", added_by="user")

    if session_store:
        session_store.append(session_id, "user", req.message)
        session_store.append(session_id, "assistant", result["response"])

    return SessionChatResponse(
        session_id=session_id,
        query=req.message,
        response=result["response"],
        sources=_normalize_sources(result.get("sources", [])),
        chunks_used=result.get("chunks_used", 0),
        response_time_ms=int((time.monotonic() - t0) * 1000),
        route_type=route_type,
    )


@app.delete("/chat/session/{session_id}", tags=["Chat"])
async def clear_session(session_id: str):
    """Xóa lịch sử hội thoại — KHÔNG xóa tri thức user (persist vĩnh viễn)."""
    if session_store:
        session_store.clear(session_id)
    return {"cleared": True, "session_id": session_id}


@app.get("/chat/history/{user_key}", response_model=ChatHistoryState, tags=["Chat"])
async def get_chat_history(user_key: str):
    """Lấy lịch sử chat đã lưu theo user_key để đồng bộ giữa nhiều trình duyệt."""
    if not session_store:
        return ChatHistoryState()
    return ChatHistoryState(**session_store.get_chat_state(user_key))


@app.put("/chat/history/{user_key}", response_model=ChatHistoryState, tags=["Chat"])
async def save_chat_history(user_key: str, state: ChatHistoryState):
    """Lưu snapshot lịch sử chat theo user_key."""
    if not session_store:
        return state
    session_store.save_chat_state(user_key, state.dict())
    return ChatHistoryState(**session_store.get_chat_state(user_key))


@app.delete("/chat/history/{user_key}/sessions/{session_id}", response_model=ChatHistoryState, tags=["Chat"])
async def delete_chat_history_session(user_key: str, session_id: str):
    """Xóa một cuộc trò chuyện khỏi lịch sử theo user_key và clear session context."""
    if not session_store:
        return ChatHistoryState()
    session_store.clear(session_id)
    return ChatHistoryState(**session_store.delete_chat_session_snapshot(user_key, session_id))


# ================================================================
# CHAT — Hybrid (Qdrant + OpenFDA + realtime + tri thức người dùng)
# ================================================================

@app.post("/chat/v2", response_model=ChatV2Response, tags=["Chat"])
async def chat_v2(req: ChatV2Request):
    """
    Endpoint chính của Streamlit UI. Gọi rag.hybrid_answer() — pipeline đầy
    đủ nhất (Qdrant + OpenFDA tra thuốc + realtime CDC + tri thức người
    dùng đã lưu qua /admin/knowledge). Nếu route này lỗi/không tồn tại,
    Streamlit sẽ fallback im lặng sang /chat/session (thiếu hết các nguồn
    trên) — nên route này PHẢI luôn hoạt động.
    """
    if not rag:
        raise HTTPException(503, "RAG pipeline chưa sẵn sàng. Chạy ingest.py trước.")
    try:
        result = await rag.hybrid_answer(
            query=req.message,
            session_id=req.session_id or "default",
            top_k=req.top_k,
            skip_llm_cache=req.skip_llm_cache,
        )
    except LLMAPIError as exc:
        raise HTTPException(502, f"LLM error: {exc}")
    except Exception as exc:
        logger.error(f"chat_v2 error: {exc}")
        raise HTTPException(500, str(exc))

    return ChatV2Response(
        query=result["query"],
        response=result["response"],
        sources=_normalize_sources(result.get("sources", [])),
        chunks_used=result.get("chunks_used", 0),
        route_type=result.get("route_type", ""),
        from_cache=result.get("from_cache", False),
        response_time_ms=result.get("response_time_ms", 0),
    )


# ================================================================
# CHAT — Streaming
# ================================================================

@app.post("/chat/stream", tags=["Chat"])
async def chat_stream(req: ChatRequest):
    if not rag:
        raise HTTPException(503, "RAG pipeline chưa sẵn sàng")

    async def generate():
        try:
            chunks = rag.retrieve(req.query, top_k=req.top_k)
            sources = list({c["metadata"].get("source", "") for c in chunks})
            yield f"data: {json.dumps({'type': 'meta', 'chunks': len(chunks), 'sources': sources}, ensure_ascii=False)}\n\n"

            text = rag.generate(req.query, chunks)
            for sentence in text.replace("**", "").split(". "):
                if sentence.strip():
                    yield f"data: {json.dumps({'type': 'text', 'content': sentence + '. '}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.03)

            yield 'data: {"type": "done"}\n\n'
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ================================================================
# SEARCH (debug)
# ================================================================

@app.get("/search", tags=["Debug"])
async def search(q: str, top_k: int = 5):
    if not store:
        raise HTTPException(503, "Store chưa sẵn sàng")
    return {"query": q, "results": store.search(q, top_k=top_k), "total": top_k}


# ================================================================
# ADMIN — User Knowledge (tri thức người dùng bổ sung, persist vĩnh viễn)
# ================================================================

class KnowledgeAddRequest(BaseModel):
    content: str = Field(..., min_length=10, max_length=8000)
    note: str = Field(default="", max_length=300)


@app.get("/admin/knowledge", tags=["Admin"])
async def list_knowledge(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """Liệt kê toàn bộ tri thức user đã bổ sung."""
    _require_key(x_admin_token, ADMIN_KEY, "list knowledge")
    if not store:
        raise HTTPException(503, "Store chưa sẵn sàng")
    items = store.list_user_knowledge()
    return {
        "total": len(items),
        "items": [
            {
                "id":           it["id"],
                "text":         it["text"],
                "added_by":     it["metadata"].get("added_by", ""),
                "note":         it["metadata"].get("note", ""),
                "indexed_date": it["metadata"].get("indexed_date", ""),
            }
            for it in items
        ],
    }


@app.post("/admin/knowledge", tags=["Admin"])
async def add_knowledge(
    req: KnowledgeAddRequest,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """Thêm tri thức mới qua API admin — persist vĩnh viễn."""
    _require_key(x_admin_token, ADMIN_KEY, "add knowledge")
    if not store:
        raise HTTPException(503, "Store chưa sẵn sàng")
    point_id = store.upsert_user_knowledge(
        text=req.content, source="admin", added_by="admin", note=req.note
    )
    return {"saved": True, "point_id": point_id}


@app.delete("/admin/knowledge/{point_id}", tags=["Admin"])
async def delete_knowledge(
    point_id: str,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """Xóa một mẩu tri thức theo point_id."""
    _require_key(x_admin_token, ADMIN_KEY, "delete knowledge")
    if not store:
        raise HTTPException(503, "Store chưa sẵn sàng")
    store.delete_user_knowledge(point_id)
    return {"deleted": True, "point_id": point_id}


# ================================================================
# ADMIN — Upload
# ================================================================

@app.post("/admin/upload", tags=["Admin"])
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(default=""),
    source_name: str = Form(default=""),
    category: str = Form(default="general"),
    language: str = Form(default="vi"),
    verified_by_doctor: bool = Form(default=False),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    _require_key(x_admin_token, ADMIN_KEY, "upload")
    if not store:
        raise HTTPException(503, "Store chưa sẵn sàng")

    from src.ingestion.loader import normalize_category
    from src.chunking.chunker import chunk_documents

    suffix = Path(file.filename).suffix.lower()
    safe_base = _safe_name(Path(file.filename).stem or source_name or "uploaded")
    document_id = f"{category}__{safe_base}"

    if suffix == ".pdf":
        target = Path("data/pdfs") / f"{document_id}.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(await file.read())
        text = extract_text_from_pdf(target)
        if not text or len(text.strip()) < 50:
            raise HTTPException(422, "PDF không đọc được text (scan PDF?)")
    else:
        text = (await file.read()).decode("utf-8", errors="ignore")

    doc = {
        "content": text, "source": source_name or safe_base,
        "category": normalize_category(category), "filename": file.filename,
        "document_id": document_id, "title": title or safe_base,
        "source_type": "uploaded", "language": language,
        "verified_by_doctor": verified_by_doctor,
        "source_url": "", "source_priority": 3, "published_date": "",
    }
    chunks = chunk_documents([doc])
    store.delete_by_document_id(document_id)
    store.upsert_chunks(chunks)
    return {"uploaded": True, "document_id": document_id, "chunks_indexed": len(chunks)}


@app.get("/admin/documents", tags=["Admin"])
async def list_documents(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    _require_key(x_admin_token, ADMIN_KEY, "list documents")
    if not store:
        raise HTTPException(503, "Store chưa sẵn sàng")
    return store.get_stats()


@app.delete("/admin/documents/{document_id}", tags=["Admin"])
async def delete_document(
    document_id: str,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    _require_key(x_admin_token, ADMIN_KEY, "delete document")
    if not store:
        raise HTTPException(503, "Store chưa sẵn sàng")
    store.delete_by_document_id(document_id)
    return {"deleted": True, "document_id": document_id}


@app.post("/admin/rebuild-index", tags=["Admin"])
async def rebuild_index(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    _require_key(x_admin_token, ADMIN_KEY, "rebuild index")
    from src.ingestion.loader import load_all_documents
    from src.chunking.chunker import chunk_documents
    from src.utils.config import cfg

    docs   = load_all_documents(cfg.paths.pdf_dir)
    chunks = chunk_documents(docs)
    fresh  = VectorStore()
    fresh.upsert_chunks(chunks)
    return {"rebuilt": True, "total_chunks": fresh.get_stats()["total_chunks"]}


# ════════════════════════════════════════════════════════
# ADMIN ROUTES
# ═══════════════════════════════════════════════════════════════
from src.retrieval.query_router import QueryRouter as _QRouter
from src.retrieval.cache_manager import get_cache as _get_cache


@app.get("/admin/route/test", tags=["Admin"])
async def test_route(
    q: str,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """Debug: xem câu hỏi được route đến nguồn nào."""
    _require_key(x_admin_token, ADMIN_KEY, "test route")
    d = _QRouter().route(q)
    return {
        "query": q, "route_type": d.route_type.value,
        "sources": d.sources, "pubmed_max": d.pubmed_max,
        "use_openfda": d.use_openfda, "drug_names": d.drug_names,
        "is_emergency": d.is_emergency, "reasoning": d.reasoning,
    }


@app.delete("/admin/cache", tags=["Admin"])
async def clear_cache(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """Xóa toàn bộ LLM answer cache (dùng sau rebuild index)."""
    _require_key(x_admin_token, ADMIN_KEY, "clear cache")
    cache = _get_cache()
    cache.invalidate_all_llm()
    return {"status": "ok", **cache.stats()}


@app.get("/admin/cache/stats", tags=["Admin"])
async def cache_stats(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    _require_key(x_admin_token, ADMIN_KEY, "cache stats")
    return _get_cache().stats()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
