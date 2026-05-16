"""Build and manage the ChromaDB vector store."""
import json
from pathlib import Path
from typing import List, Optional

from langchain_core.documents import Document
from rich.console import Console
from config.settings import CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL

console = Console()
_vectorstore = None
_embedding_model = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    console.print(f"[blue]→[/blue] Loading embedding model: {EMBEDDING_MODEL}")
    try:                                            # mới (không warning)
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:                             # fallback cũ
        from langchain_community.embeddings import HuggingFaceEmbeddings
    _embedding_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    return _embedding_model


def _chroma(embeddings, persist_dir):
    """Lấy class Chroma mới nhất, không warning."""
    try:
        from langchain_chroma import Chroma
    except ImportError:
        from langchain_community.vectorstores import Chroma
    return Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=persist_dir,
        embedding_function=embeddings,
    )


def _chroma_from_docs(docs, embeddings, persist_dir):
    try:
        from langchain_chroma import Chroma
    except ImportError:
        from langchain_community.vectorstores import Chroma
    return Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=persist_dir,
    )


def build_vectorstore(chunks: List[Document]):
    if not chunks:
        raise ValueError(
            "Danh sách chunks rỗng!\n"
            "Kiểm tra: scraper VN, thư mục PDF, hoặc file CSV."
        )

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    embeddings  = get_embedding_model()
    persist_dir = str(CHROMA_DIR)

    console.print(f"[blue]→[/blue] Embedding [bold]{len(chunks)}[/bold] chunks vào ChromaDB …")

    BATCH = 100
    vs = _chroma_from_docs(chunks[:BATCH], embeddings, persist_dir)
    for i in range(BATCH, len(chunks), BATCH):
        vs.add_documents(chunks[i:i+BATCH])
        console.print(f"[dim]  {min(i+BATCH, len(chunks))}/{len(chunks)} chunks[/dim]")

    count = vs._collection.count()
    console.print(f"[green]✓[/green] {count} vectors lưu tại {CHROMA_DIR}")
    return vs


def load_vectorstore():
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    embeddings  = get_embedding_model()
    _vectorstore = _chroma(embeddings, str(CHROMA_DIR))

    try:
        count = _vectorstore._collection.count()
        if count == 0:
            console.print("[yellow]⚠ Vectorstore rỗng — chạy: python main.py --build[/yellow]")
        else:
            console.print(f"[green]✓[/green] Loaded vectorstore: {count} vectors")
    except Exception:
        pass
    return _vectorstore


def add_json_documents(json_path, vectorstore):
    with open(json_path, encoding="utf-8") as f:
        raw = json.load(f)
    docs = [Document(page_content=d["page_content"], metadata=d["metadata"]) for d in raw]
    vectorstore.add_documents(docs)
    console.print(f"[green]✓[/green] Added {len(docs)} docs từ {json_path}")
