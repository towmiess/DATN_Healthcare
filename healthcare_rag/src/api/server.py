"""
================================================================
BƯỚC 5: API SERVER — FastAPI Backend
================================================================

Cung cấp REST API để frontend hoặc mobile app gọi vào.

Endpoints:
  GET  /health         → Kiểm tra server hoạt động
  GET  /stats          → Thống kê vector DB
  POST /chat           → Hỏi chatbot (single turn)
  POST /chat/stream    → Hỏi chatbot (streaming response)
  POST /chat/history   → Hỏi chatbot (multi-turn)

CÁCH CHẠY:
  uvicorn src.api.server:app --reload --port 8000

SWAGGER UI (test API):
  http://localhost:8000/docs
================================================================
"""

import os
import sys
import time
import asyncio
import json
from pathlib import Path
from typing import List, Optional
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.rag.pipeline import LLMAPIError, RAGPipeline
from src.rag.indexer import VectorIndexer, extract_text_from_pdf

# ── Khởi tạo FastAPI ────────────────────────────────────────
app = FastAPI(
    title="🏥 Healthcare RAG Chatbot API",
    description="Hệ thống tư vấn y tế tiểu đường dựa trên RAG + Gemini 2.5 Flash",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS: cho phép frontend (localhost:3000, v.v.) gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Production: đổi thành domain cụ thể
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global objects (khởi tạo 1 lần khi start server) ────────
rag_pipeline: Optional[RAGPipeline] = None
indexer: Optional[VectorIndexer] = None
FRONTEND_INDEX = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "healthcare-admin-dev")
DOCTOR_SECRET_KEY = os.getenv("DOCTOR_SECRET_KEY", "healthcare-doctor-dev")

if os.getenv("ADMIN_SECRET_KEY", "") == "":
    logger.warning("ADMIN_SECRET_KEY chua cau hinh, dang dung fallback local dev secret")
if os.getenv("DOCTOR_SECRET_KEY", "") == "":
    logger.warning("DOCTOR_SECRET_KEY chua cau hinh, dang dung fallback local dev secret")


@app.on_event("startup")
async def startup_event():
    """Khởi tạo RAG pipeline khi server start."""
    global rag_pipeline, indexer
    logger.info("🚀 Đang khởi động Healthcare RAG Server...")
    try:
        indexer = VectorIndexer()
        stats = indexer.get_stats()
        if stats["total_chunks"] == 0:
            logger.warning("⚠ Vector DB trống! Chạy indexer.py trước.")
        else:
            rag_pipeline = RAGPipeline()
            logger.success(f"✅ Server sẵn sàng! ({stats['total_chunks']} chunks)")
    except Exception as e:
        logger.error(f"❌ Lỗi khởi động: {e}")


# ================================================================
# PYDANTIC MODELS — Định nghĩa request/response schema
# ================================================================

class ChatRequest(BaseModel):
    """Request body cho /chat."""
    query: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Câu hỏi về sức khỏe tiểu đường",
        example="Tôi bị tiểu đường type 2, ăn phở được không?"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Số tài liệu tham khảo (1-10)"
    )
    patient_context: Optional[dict] = Field(
        default=None,
        description="Hồ sơ bệnh nhân do hệ thống chung truyền sang"
    )


class MessageItem(BaseModel):
    """Một tin nhắn trong lịch sử hội thoại."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)


class ChatHistoryRequest(BaseModel):
    """Request body cho /chat/history (multi-turn)."""
    messages: List[MessageItem] = Field(
        ...,
        min_length=1,
        description="Lịch sử hội thoại"
    )
    top_k: int = Field(default=5, ge=1, le=10)
    patient_context: Optional[dict] = Field(
        default=None,
        description="Hồ sơ bệnh nhân do hệ thống chung truyền sang"
    )


class SourceInfo(BaseModel):
    """Thông tin nguồn tài liệu."""
    source: str
    category: str = ""
    similarity: float = 0.0


class ChatResponse(BaseModel):
    """Response body cho /chat."""
    query: str
    response: str
    sources: List[SourceInfo]
    chunks_used: int
    response_time_ms: int


class DoctorNoteCreate(BaseModel):
    category: str = Field(..., min_length=1)
    text: str = Field(..., min_length=10, max_length=4000)
    doctor_name: str = Field(..., min_length=2, max_length=120)
    specialty: str = Field(default="", max_length=120)


class DoctorNoteUpdate(BaseModel):
    category: Optional[str] = Field(default=None, min_length=1)
    text: Optional[str] = Field(default=None, min_length=10, max_length=4000)
    doctor_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    specialty: Optional[str] = Field(default=None, max_length=120)
    status: Optional[str] = Field(default=None, max_length=32)


# ================================================================
# ENDPOINTS
# ================================================================

@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the bundled chatbot UI."""
    if not FRONTEND_INDEX.exists():
        return JSONResponse(
            status_code=404,
            content={"detail": f"Frontend not found: {FRONTEND_INDEX}"},
        )
    return FileResponse(FRONTEND_INDEX)


def _require_secret(provided: Optional[str], expected: str, label: str):
    if not expected:
        raise HTTPException(503, detail=f"{label} chua duoc cau hinh")
    if provided != expected:
        raise HTTPException(403, detail=f"Khong du quyen {label}")


def _doctor_note_to_response(note_id: str, metadata: dict, text: str) -> dict:
    return {
        "id": note_id,
        "text": text,
        "category": metadata.get("category", ""),
        "doctor_name": metadata.get("doctor_name", ""),
        "specialty": metadata.get("specialty", ""),
        "status": metadata.get("note_status", "active"),
        "source_type": metadata.get("source_type", "doctor_note"),
        "verified_by_doctor": metadata.get("verified_by_doctor", True),
        "published_date": metadata.get("published_date", ""),
        "indexed_date": metadata.get("indexed_date", ""),
    }


def _flatten_chroma_result(values):
    if not values:
        return []
    first = values[0]
    if isinstance(first, list):
        return first
    return values


def _safe_filename(name: str) -> str:
    keep = []
    for ch in name:
        if ch.isalnum() or ch in {"-", "_", ".", " "}:
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip().replace(" ", "_")


def _remove_document_files(document_id: str) -> list[str]:
    removed = []
    stem = _safe_filename(document_id)
    for folder, suffix in ((Path("data/raw"), ".txt"), (Path("data/pdfs"), ".pdf")):
        target = folder / f"{stem}{suffix}"
        if target.exists():
            target.unlink()
            removed.append(str(target))
    return removed


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/health", tags=["System"])
async def health_check():
    """Kiểm tra server hoạt động."""
    global rag_pipeline, indexer
    status = "ready" if rag_pipeline else "no_data"
    chunks = indexer.get_stats()["total_chunks"] if indexer else 0
    return {
        "status": status,
        "total_chunks": chunks,
        "message": "RAG Pipeline sẵn sàng" if rag_pipeline else "Cần chạy indexer trước",
    }


@app.get("/stats", tags=["System"])
async def get_stats():
    """Thống kê chi tiết về Vector Database."""
    global indexer
    if not indexer:
        raise HTTPException(503, "Vector DB chưa khởi động")
    return indexer.get_stats()


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Hỏi chatbot y tế (single turn).

    Gửi câu hỏi → nhận câu trả lời có nguồn tham khảo.
    """
    global rag_pipeline
    if not rag_pipeline:
        raise HTTPException(
            503,
            detail="RAG Pipeline chưa sẵn sàng. Hãy chạy indexer.py trước!"
        )

    start_time = time.time()
    try:
        result = rag_pipeline.answer(
            request.query,
            top_k=request.top_k,
            patient_context=request.patient_context,
        )
        elapsed_ms = int((time.time() - start_time) * 1000)

        return ChatResponse(
            query=result["query"],
            response=result["response"],
            sources=[SourceInfo(**s) for s in result["sources"]],
            chunks_used=result["chunks_used"],
            response_time_ms=elapsed_ms,
        )
    except LLMAPIError as e:
        logger.error(f"Gemini API error: {e}")
        status_code = 503 if e.retryable else 502
        detail = (
            f"Lỗi LLM API tạm thời, vui lòng thử lại sau: {str(e)}"
            if e.retryable
            else f"Lỗi LLM API: {str(e)}"
        )
        raise HTTPException(status_code, detail)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(500, f"Lỗi server: {str(e)}")


@app.post("/chat/stream", tags=["Chat"])
async def chat_stream(request: ChatRequest):
    """
    Hỏi chatbot với streaming response (text xuất hiện dần).

    Dùng Server-Sent Events (SSE) — text stream về từng chunk.
    Frontend nhận và hiển thị realtime như ChatGPT.
    """
    global rag_pipeline, indexer
    if not rag_pipeline and not indexer:
        raise HTTPException(503, "Service chưa sẵn sàng")

    async def generate():
        try:
            if not rag_pipeline:
                yield "data: [ERROR]RAG Pipeline chưa sẵn sàng[/ERROR]\n\n"
                return

            result = rag_pipeline.answer(
                request.query,
                top_k=request.top_k,
                patient_context=request.patient_context,
            )
            for word in result["response"].split(" "):
                yield f"data: {word} \n\n"

            # Gửi sources ở cuối
            sources = [s["source"] for s in result["sources"][:3]]
            yield f"data: [SOURCES]{','.join(sources)}[/SOURCES]\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: [ERROR]{str(e)}[/ERROR]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/chat/history", response_model=ChatResponse, tags=["Chat"])
async def chat_with_history(request: ChatHistoryRequest):
    """
    Hỏi chatbot với lịch sử hội thoại (multi-turn).

    Gửi toàn bộ conversation history để chatbot nhớ ngữ cảnh.
    """
    global rag_pipeline
    if not rag_pipeline:
        raise HTTPException(503, "RAG Pipeline chưa sẵn sàng")

    start_time = time.time()
    try:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        result = rag_pipeline.answer_with_history(
            messages,
            top_k=request.top_k,
            patient_context=request.patient_context,
        )
        elapsed_ms = int((time.time() - start_time) * 1000)

        return ChatResponse(
            query=result["query"],
            response=result["response"],
            sources=[SourceInfo(**s) if isinstance(s, dict) else SourceInfo(source=str(s))
                     for s in result["sources"]],
            chunks_used=result["chunks_used"],
            response_time_ms=elapsed_ms,
        )
    except LLMAPIError as e:
        logger.error(f"Gemini API error: {e}")
        status_code = 503 if e.retryable else 502
        detail = (
            f"Lỗi LLM API tạm thời, vui lòng thử lại sau: {str(e)}"
            if e.retryable
            else f"Lỗi LLM API: {str(e)}"
        )
        raise HTTPException(status_code, detail)
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(500, str(e))


@app.post("/admin/doctor-notes", tags=["Admin"])
async def create_doctor_note(
    request: DoctorNoteCreate,
    x_doctor_token: Optional[str] = Header(default=None, alias="X-Doctor-Token"),
):
    global indexer
    _require_secret(x_doctor_token, DOCTOR_SECRET_KEY, "doctor notes")
    if not indexer:
        raise HTTPException(503, "Indexer chua san sang")

    result = indexer.add_doctor_note(
        text=request.text,
        category=request.category,
        doctor_name=request.doctor_name,
        specialty=request.specialty,
    )
    return result


@app.get("/admin/doctor-notes", tags=["Admin"])
async def list_doctor_notes(
    x_doctor_token: Optional[str] = Header(default=None, alias="X-Doctor-Token"),
):
    global indexer
    _require_secret(x_doctor_token, DOCTOR_SECRET_KEY, "doctor notes")
    if not indexer:
        raise HTTPException(503, "Indexer chua san sang")

    data = indexer.collection.get(
        where={"source_type": {"$eq": "doctor_note"}},
        include=["documents", "metadatas"],
    )
    notes = []
    ids = _flatten_chroma_result(data.get("ids"))
    docs = _flatten_chroma_result(data.get("documents"))
    metas = _flatten_chroma_result(data.get("metadatas"))
    for note_id, text, meta in zip(ids, docs, metas):
        notes.append(_doctor_note_to_response(note_id, meta, text))
    return {"total": len(notes), "items": notes}


@app.put("/admin/doctor-notes/{note_id}", tags=["Admin"])
async def update_doctor_note(
    note_id: str,
    request: DoctorNoteUpdate,
    x_doctor_token: Optional[str] = Header(default=None, alias="X-Doctor-Token"),
):
    global indexer
    _require_secret(x_doctor_token, DOCTOR_SECRET_KEY, "doctor notes")
    if not indexer:
        raise HTTPException(503, "Indexer chua san sang")

    current = indexer.collection.get(ids=[note_id], include=["documents", "metadatas"])
    if not current.get("ids") or not current["ids"][0]:
        raise HTTPException(404, "Doctor note khong ton tai")

    old_text = current["documents"][0][0]
    old_meta = current["metadatas"][0][0]
    new_text = request.text or old_text
    new_meta = dict(old_meta)
    if request.category is not None:
        new_meta["category"] = request.category
    if request.doctor_name is not None:
        new_meta["doctor_name"] = request.doctor_name
    if request.specialty is not None:
        new_meta["specialty"] = request.specialty
    if request.status is not None:
        new_meta["note_status"] = request.status

    indexer.collection.update(ids=[note_id], documents=[new_text], metadatas=[new_meta])
    return _doctor_note_to_response(note_id, new_meta, new_text)


@app.delete("/admin/doctor-notes/{note_id}", tags=["Admin"])
async def delete_doctor_note(
    note_id: str,
    x_doctor_token: Optional[str] = Header(default=None, alias="X-Doctor-Token"),
):
    global indexer
    _require_secret(x_doctor_token, DOCTOR_SECRET_KEY, "doctor notes")
    if not indexer:
        raise HTTPException(503, "Indexer chua san sang")

    deleted = indexer.delete_document(note_id)
    if not deleted:
        raise HTTPException(404, "Doctor note khong ton tai")
    return {"deleted": True, "id": note_id}


@app.post("/admin/documents/upload", tags=["Admin"])
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(default=""),
    source_name: str = Form(default=""),
    source_type: str = Form(default="web_crawled"),
    category: str = Form(default="general"),
    language: str = Form(default="vi"),
    published_date: str = Form(default=""),
    verified_by_doctor: bool = Form(default=False),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    _require_secret(x_admin_token, ADMIN_SECRET_KEY, "document upload")
    global indexer
    if not indexer:
        raise HTTPException(503, "Indexer chua san sang")

    suffix = Path(file.filename).suffix.lower()
    safe_base = _safe_filename(Path(file.filename).stem or source_name or title or "uploaded_document")
    document_id = f"{category}__{safe_base}"
    indexed = False
    chunks_indexed = 0

    if suffix == ".pdf":
        target = Path("data/pdfs") / f"{document_id}.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        content = await file.read()
        target.write_bytes(content)
        kind = "pdf"

        try:
            extracted = extract_text_from_pdf(target)
            if extracted and len(extracted.strip()) >= 100:
                index_result = indexer.index_uploaded_document(
                    text=extracted,
                    document_id=document_id,
                    title=title or source_name or safe_base,
                    source_name=source_name or safe_base,
                    source_type=source_type,
                    category=category,
                    language=language,
                    published_date=published_date,
                    verified_by_doctor=verified_by_doctor,
                    filename=target.name,
                )
                indexed = True
                chunks_indexed = index_result.get("chunks_indexed", 0)
        except Exception as exc:
            logger.warning(f"Khong index ngay duoc PDF upload {document_id}: {exc}")
    else:
        raw_target = Path("data/raw") / f"{document_id}.txt"
        raw_target.parent.mkdir(parents=True, exist_ok=True)
        body = (await file.read()).decode("utf-8", errors="ignore")
        metadata = {
            "source_name": source_name or safe_base,
            "document_title": title or source_name or safe_base,
            "url": "",
            "category": category,
            "language": language,
            "source_type": source_type,
            "source_priority": 3 if verified_by_doctor else 4,
            "verified_by_doctor": verified_by_doctor,
            "published_date": published_date,
            "condition_tags": [category],
            "crawled_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "char_count": len(body),
        }
        raw_target.write_text(
            "===METADATA===\n"
            + json.dumps(metadata, ensure_ascii=False, indent=2)
            + "\n===CONTENT===\n"
            + body,
            encoding="utf-8",
        )
        kind = "txt"

        try:
            index_result = indexer.index_uploaded_document(
                text=body,
                document_id=document_id,
                title=title or source_name or safe_base,
                source_name=source_name or safe_base,
                source_type=source_type,
                category=category,
                language=language,
                published_date=published_date,
                verified_by_doctor=verified_by_doctor,
                filename=raw_target.name,
            )
            indexed = True
            chunks_indexed = index_result.get("chunks_indexed", 0)
        except Exception as exc:
            logger.warning(f"Khong index ngay duoc TXT upload {document_id}: {exc}")

    return {
        "uploaded": True,
        "document_id": document_id,
        "kind": kind,
        "file_name": file.filename,
        "title": title or source_name or safe_base,
        "indexed": indexed,
        "chunks_indexed": chunks_indexed,
    }


@app.get("/admin/documents", tags=["Admin"])
async def list_documents(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _require_secret(x_admin_token, ADMIN_SECRET_KEY, "document listing")
    global indexer
    if not indexer:
        raise HTTPException(503, "Indexer chua san sang")

    data = indexer.collection.get(include=["documents", "metadatas"])
    ids = _flatten_chroma_result(data.get("ids"))
    docs = _flatten_chroma_result(data.get("documents"))
    metas = _flatten_chroma_result(data.get("metadatas"))

    items = []
    seen = set()
    for doc_id, text, meta in zip(ids, docs, metas):
        if meta.get("source_type") in {"user", "user_knowledge", "user_response_rule"}:
            continue
        document_id = meta.get("document_id") or doc_id
        if document_id in seen:
            continue
        seen.add(document_id)
        items.append({
            "document_id": document_id,
            "title": meta.get("document_title", ""),
            "source": meta.get("source", ""),
            "source_type": meta.get("source_type", ""),
            "category": meta.get("category", ""),
            "language": meta.get("language", ""),
            "verified_by_doctor": meta.get("verified_by_doctor", False),
            "published_date": meta.get("published_date", ""),
            "chunks": meta.get("total_chunks", 1),
        })

    return {"total": len(items), "items": items}


@app.delete("/admin/documents/{document_id}", tags=["Admin"])
async def delete_document(
    document_id: str,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    _require_secret(x_admin_token, ADMIN_SECRET_KEY, "document deletion")
    global indexer
    if not indexer:
        raise HTTPException(503, "Indexer chua san sang")

    data = indexer.collection.get(where={"document_id": {"$eq": document_id}}, include=["metadatas"])
    ids = _flatten_chroma_result(data.get("ids"))
    if not ids:
        raise HTTPException(404, "Document khong ton tai")

    indexer.collection.delete(where={"document_id": {"$eq": document_id}})
    removed_files = _remove_document_files(document_id)
    return {"deleted": True, "document_id": document_id, "removed_files": removed_files, "chunks_removed": len(ids)}


@app.post("/admin/rebuild-index", tags=["Admin"])
async def rebuild_index(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _require_secret(x_admin_token, ADMIN_SECRET_KEY, "index rebuild")
    from src.preprocessor.pdf_builder import PDFBuilder
    from src.rag.indexer import load_all_pdfs, chunk_documents, VectorIndexer

    builder = PDFBuilder()
    builder.build_all()
    docs = load_all_pdfs(Path("data/pdfs"))
    chunks = chunk_documents(docs)
    fresh_indexer = VectorIndexer()
    fresh_indexer.index_chunks(chunks)
    stats = fresh_indexer.get_stats()
    return {"rebuilt": True, "total_chunks": stats["total_chunks"], "categories": stats["categories"]}


@app.get("/search", tags=["Debug"])
async def search_docs(q: str, top_k: int = 5):
    """
    Tìm kiếm trực tiếp trong Vector DB (để debug).

    Trả về các chunk liên quan mà không qua LLM.
    """
    global indexer
    if not indexer:
        raise HTTPException(503, "Indexer chưa sẵn sàng")

    chunks = indexer.search(q, top_k=top_k)
    return {
        "query": q,
        "results": chunks,
        "total": len(chunks),
    }


# ── CHẠY TRỰC TIẾP ──────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 8000))
    logger.info(f"🌐 Khởi động server tại http://{host}:{port}")
    logger.info(f"📖 Swagger UI: http://localhost:{port}/docs")
    uvicorn.run("src.api.server:app", host=host, port=port, reload=True)
