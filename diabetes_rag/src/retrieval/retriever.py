"""Smart retriever — ChromaDB $and filter syntax, graceful fallback."""
from typing import List, Optional
from langchain_core.documents import Document
from rich.console import Console
from config.settings import RETRIEVAL_TOP_K, FETCH_K
from src.chunking.metadata_enricher import detect_topic

console = Console()


def build_chroma_filter(topic: str = None, language: str = None) -> Optional[dict]:
    """
    ChromaDB filter đúng cú pháp:
    - 1 field  → {"field": {"$eq": value}}
    - 2 fields → {"$and": [{...}, {...}]}
    """
    conds = []
    if topic and topic != "general":
        conds.append({"topic": {"$eq": topic}})
    if language == "vi":
        conds.append({"language": {"$eq": "vi"}})

    if not conds:       return None
    if len(conds) == 1: return conds[0]
    return {"$and": conds}


def _get_retriever(vectorstore, filt, k=None):
    return vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": k or RETRIEVAL_TOP_K,
            "fetch_k": FETCH_K,
            "filter": filt,
            "lambda_mult": 0.7,
        },
    )


def retrieve(
    query: str,
    vectorstore,
    language: str = "en",
    force_topic: Optional[str] = None,
) -> List[Document]:
    topic = force_topic or detect_topic(query)

    # ── Thử 1: filter đầy đủ (topic + language) ───────────────────────────
    filt = build_chroma_filter(topic=topic, language=language)
    console.print(f"[dim]Retriever: topic={topic}, language={language}, filter={filt}[/dim]")
    chunks = []
    if filt:
        try:
            chunks = _get_retriever(vectorstore, filt).invoke(query)
        except Exception as e:
            console.print(f"[yellow]⚠ Retrieval with filter failed: {e}[/yellow]")

    # ── Thử 2: chỉ filter topic (bỏ language) ─────────────────────────────
    if not chunks and topic != "general":
        filt2 = build_chroma_filter(topic=topic)
        console.print(f"[yellow]⚠ 0 chunks — retry topic-only filter: {filt2}[/yellow]")
        try:
            chunks = _get_retriever(vectorstore, filt2).invoke(query)
        except Exception as e:
            console.print(f"[yellow]⚠ Topic-only filter failed: {e}[/yellow]")

    # ── Thử 3: không filter gì cả ─────────────────────────────────────────
    if not chunks:
        console.print("[yellow]⚠ 0 chunks — retry without any filter[/yellow]")
        try:
            chunks = _get_retriever(vectorstore, None).invoke(query)
        except Exception as e:
            console.print(f"[red]✗ No-filter retrieval failed: {e}[/red]")

    if chunks:
        console.print(f"[green]✓[/green] Retrieved {len(chunks)} chunks for: '{query[:60]}'")
        for i, c in enumerate(chunks, 1):
            src = c.metadata.get("source", "?")
            tp  = c.metadata.get("topic",  "?")
            console.print(f"  [{i}] {src} | {tp} — {c.page_content[:70]}…")
    else:
        console.print("[red]✗ Không tìm thấy chunk nào. Vectorstore có thể rỗng.[/red]")
        console.print("[yellow]→ Chạy: python main.py --build[/yellow]")

    return chunks
