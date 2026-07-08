"""
================================================================
API SERVER — FastAPI Backend
================================================================

Endpoints:
  GET  /health              → Kiểm tra server
  GET  /stats               → Thống kê vector DB
  POST /chat                → Hỏi chatbot (single turn)
  POST /chat/stream         → Streaming response
  POST /chat/session        → Multi-turn với Redis session
  POST /admin/upload        → Upload PDF/TXT mới
  GET  /admin/documents     → Danh sách tài liệu
  DELETE /admin/documents/{id} → Xóa tài liệu
  GET  /search              → Debug tìm kiếm vector

Swagger UI: http://localhost:8000/docs
================================================================
"""

import os
import sys
import time
import json
import uuid
import asyncio
from pathlib import Path
from typing import List, Optional
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.rag.pipeline import RAGPipeline, LLMAPIError, detect_intent
from src.rag.indexer import VectorIndexer, extract_text_from_pdf
from src.rag.session import SessionStore

# ── Khởi tạo App ────────────────────────────────────────────
app = FastAPI(
    title="🏥 Healthcare RAG API v2",
    description="Chatbot tư vấn tiểu đường — RAG + Gemini + Qdrant + Redis",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ADMIN_KEY  = os.getenv("ADMIN_SECRET_KEY", "healthcare-admin-dev")
DOCTOR_KEY = os.getenv("DOCTOR_SECRET_KEY", "healthcare-doctor-dev")

# Global singletons
rag: Optional[RAGPipeline] = None
indexer: Optional[VectorIndexer] = None
session_store: Optional[SessionStore] = None


@app.on_event("startup")
async def startup():
    global rag, indexer, session_store
    logger.info("🚀 Khởi động Healthcare RAG Server v2...")
    try:
        session_store = SessionStore()
        indexer = VectorIndexer()
        stats = indexer.get_stats()
        if stats["total_chunks"] == 0:
            logger.warning("⚠ Vector DB trống! Chạy: python scripts/ingest.py")
        else:
            rag = RAGPipeline()
            logger.success(f"✅ Server sẵn sàng! ({stats['total_chunks']} chunks)")
    except Exception as e:
        logger.error(f"❌ Lỗi khởi động: {e}")


def _require_key(token: Optional[str], expected: str, action: str):
    if token != expected:
        raise HTTPException(403, f"Không có quyền: {action}")


def _safe_filename(name: str) -> str:
    import re
    return re.sub(r"[^\w\-.]", "_", name)[:80]


# ================================================================
# SCHEMAS
# ================================================================

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000,
                       example="Tôi bị tiểu đường type 2, ăn phở được không?")
    top_k: int = Field(default=4, ge=1, le=10)
    patient_context: Optional[dict] = None


class SessionChatRequest(BaseModel):
    session_id: Optional[str] = Field(default=None, description="Bỏ trống để tạo session mới")
    message: str = Field(..., min_length=3, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=10)


class SourceInfo(BaseModel):
    source: str
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


# ================================================================
# HEALTH & STATS
# ================================================================

@app.get("/health", tags=["System"])
async def health():
    stats = indexer.get_stats() if indexer else {}
    return {
        "status": "ok",
        "rag_ready": rag is not None,
        "total_chunks": stats.get("total_chunks", 0),
        "session_store": "redis" if (session_store and session_store.redis_enabled) else "memory",
    }


@app.get("/stats", tags=["System"])
async def stats():
    if not indexer:
        raise HTTPException(503, "Indexer chưa sẵn sàng")
    return indexer.get_stats()


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
    except LLMAPIError as e:
        raise HTTPException(502, f"LLM error: {e}")
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(500, str(e))

    return ChatResponse(
        query=result["query"],
        response=result["response"],
        sources=[SourceInfo(**s) for s in result.get("sources", [])],
        chunks_used=result.get("chunks_used", 0),
        response_time_ms=int((time.monotonic() - t0) * 1000),
        intent=detect_intent(req.query),
    )


# ================================================================
# CHAT — Multi-turn với Redis Session
# ================================================================

@app.post("/chat/session", response_model=SessionChatResponse, tags=["Chat"])
async def chat_session(req: SessionChatRequest):
    if not rag:
        raise HTTPException(503, "RAG pipeline chưa sẵn sàng")

    # Tạo hoặc dùng session_id hiện có
    session_id = req.session_id or str(uuid.uuid4())
    history = session_store.get_history(session_id) if session_store else []

    # Thêm tin nhắn user vào history
    history.append({"role": "user", "content": req.message})

    t0 = time.monotonic()
    try:
        result = rag.answer_with_history(history, top_k=req.top_k)
    except LLMAPIError as e:
        raise HTTPException(502, f"LLM error: {e}")
    except Exception as e:
        logger.error(f"Session chat error: {e}")
        raise HTTPException(500, str(e))

    # Lưu assistant response vào session
    if session_store:
        session_store.append(session_id, "user", req.message)
        session_store.append(session_id, "assistant", result["response"])

    return SessionChatResponse(
        session_id=session_id,
        query=req.message,
        response=result["response"],
        sources=[SourceInfo(**s) if isinstance(s, dict) else SourceInfo(source=s.get("source", ""))
                 for s in result.get("sources", [])],
        chunks_used=result.get("chunks_used", 0),
        response_time_ms=int((time.monotonic() - t0) * 1000),
    )


@app.delete("/chat/session/{session_id}", tags=["Chat"])
async def clear_session(session_id: str):
    if session_store:
        session_store.clear(session_id)
    return {"cleared": True, "session_id": session_id}


# ================================================================
# CHAT — Streaming
# ================================================================

@app.post("/chat/stream", tags=["Chat"])
async def chat_stream(req: ChatRequest):
    if not rag:
        raise HTTPException(503, "RAG pipeline chưa sẵn sàng")

    async def generate():
        try:
            # Retrieve chunks
            chunks = rag.retrieve(req.query, top_k=req.top_k)
            sources = list({c["metadata"].get("source", "") for c in chunks})

            # Emit metadata trước
            meta = json.dumps({"type": "meta", "chunks": len(chunks), "sources": sources}, ensure_ascii=False)
            yield f"data: {meta}\n\n"

            # Generate full (Gemini không native stream với REST, simulate theo câu)
            result = rag.generate(req.query, chunks)
            sentences = result.replace("**", "").split(". ")
            for sentence in sentences:
                if sentence.strip():
                    chunk_data = json.dumps({"type": "text", "content": sentence + ". "}, ensure_ascii=False)
                    yield f"data: {chunk_data}\n\n"
                    await asyncio.sleep(0.03)

            yield 'data: {"type": "done"}\n\n'

        except Exception as e:
            error = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
            yield f"data: {error}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ================================================================
# SEARCH — Debug
# ================================================================

@app.get("/search", tags=["Debug"])
async def search(q: str, top_k: int = 5):
    if not indexer:
        raise HTTPException(503, "Indexer chưa sẵn sàng")
    chunks = indexer.search(q, top_k=top_k)
    return {"query": q, "results": chunks, "total": len(chunks)}


# ================================================================
# ADMIN — Upload tài liệu
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
    _require_key(x_admin_token, ADMIN_KEY, "document upload")
    if not indexer:
        raise HTTPException(503, "Indexer chưa sẵn sàng")

    suffix = Path(file.filename).suffix.lower()
    safe_base = _safe_filename(Path(file.filename).stem or source_name or "uploaded")
    document_id = f"{category}__{safe_base}"

    if suffix == ".pdf":
        target = Path("data/pdfs") / f"{document_id}.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(await file.read())
        extracted = extract_text_from_pdf(target)
        if not extracted or len(extracted.strip()) < 100:
            raise HTTPException(422, "PDF không đọc được text (có thể là file scan)")
        text = extracted
    else:
        text = (await file.read()).decode("utf-8", errors="ignore")

    result = indexer.index_uploaded_document(
        text=text,
        document_id=document_id,
        title=title or source_name or safe_base,
        source_name=source_name or safe_base,
        source_type="uploaded",
        category=category,
        language=language,
        verified_by_doctor=verified_by_doctor,
        filename=file.filename,
    )
    return {"uploaded": True, "document_id": document_id, "chunks_indexed": result["chunks_indexed"]}


@app.get("/admin/documents", tags=["Admin"])
async def list_documents(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    _require_key(x_admin_token, ADMIN_KEY, "list documents")
    if not indexer:
        raise HTTPException(503, "Indexer chưa sẵn sàng")

    stats = indexer.get_stats()
    return {
        "total_chunks": stats["total_chunks"],
        "categories": stats.get("categories", {}),
        "embedding_model": stats.get("embedding_model", ""),
    }


@app.delete("/admin/documents/{document_id}", tags=["Admin"])
async def delete_document(
    document_id: str,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    _require_key(x_admin_token, ADMIN_KEY, "delete document")
    if not indexer:
        raise HTTPException(503, "Indexer chưa sẵn sàng")

    from qdrant_client.models import Filter, FieldCondition, MatchValue
    indexer.client.delete(
        collection_name=indexer.COLLECTION_NAME if hasattr(indexer, "COLLECTION_NAME") else "healthcare_diabetes",
        points_selector=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
        ),
    )
    return {"deleted": True, "document_id": document_id}


@app.post("/admin/rebuild-index", tags=["Admin"])
async def rebuild_index(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    _require_key(x_admin_token, ADMIN_KEY, "rebuild index")
    from src.rag.indexer import load_all_pdfs, chunk_documents
    docs = load_all_pdfs(Path("data/pdfs"))
    chunks = chunk_documents(docs)
    fresh = VectorIndexer()
    fresh.index_chunks(chunks)
    stats = fresh.get_stats()
    return {"rebuilt": True, "total_chunks": stats["total_chunks"]}


# ── Run ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
