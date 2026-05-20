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
from pathlib import Path
from typing import List, Optional
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.rag.pipeline import LLMAPIError, RAGPipeline
from src.rag.indexer import VectorIndexer

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
        result = rag_pipeline.answer(request.query, top_k=request.top_k)
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

            result = rag_pipeline.answer(request.query, top_k=request.top_k)
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
        result = rag_pipeline.answer_with_history(messages, top_k=request.top_k)
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
