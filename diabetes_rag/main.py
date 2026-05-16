"""
Diabetes RAG System — Main Entry Point
=======================================
Runs the full pipeline:
  1. Scrape Vietnamese food data
  2. Load all documents
  3. Chunk + enrich with metadata
  4. Build vector store
  5. Start interactive query loop

Usage:
  python main.py                # interactive query mode
  python main.py --build        # (re)build the index from scratch
  python main.py --eval         # run evaluation suite
"""
import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

console = Console()


def build_index():
    """Full ingestion + embedding pipeline."""
    import json
    from langchain_core.documents import Document
    from src.ingestion.scraper_vn import run_scraper
    from src.chunking.chunker import chunk_documents
    from src.chunking.metadata_enricher import enrich
    from src.retrieval.vectorstore import build_vectorstore
    from config.settings import RAW_DIR, PROCESSED_DIR

    all_chunks = []

    # ── Step 1: Vietnamese food data (ALWAYS runs — built-in DB) ─────────────
    console.rule("[bold]Step 1: Vietnamese Food Data")
    run_scraper()   # → saves data/processed/vn_foods_documents.json

    vn_json = PROCESSED_DIR / "vn_foods_documents.json"
    if vn_json.exists():
        with open(vn_json, encoding="utf-8") as f:
            raw = json.load(f)
        vn_chunks = [Document(page_content=d["page_content"], metadata=d["metadata"]) for d in raw]
        all_chunks.extend(vn_chunks)
        console.print(f"[green]✓[/green] Loaded {len(vn_chunks)} Vietnamese food chunks")
    else:
        console.print("[red]✗ vn_foods_documents.json not found — scraper may have failed[/red]")

    # ── Step 2: PDF guidelines (optional — add ADA/WHO PDFs here) ────────────
    console.rule("[bold]Step 2: Clinical Guidelines (PDF)")
    pdf_dir = RAW_DIR / "guidelines"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_files = list(pdf_dir.glob("*.pdf"))
    if pdf_files:
        from src.ingestion.load_pdfs import load_pdf
        for pdf_path in pdf_files:
            source_name = pdf_path.stem.upper().replace("_", " ")
            docs   = load_pdf(pdf_path)
            chunks = chunk_documents(docs, doc_type="guideline")
            chunks = enrich(chunks, source_name=source_name, doc_type="guideline")
            all_chunks.extend(chunks)
            console.print(f"[green]✓[/green] {pdf_path.name}: {len(chunks)} chunks")
    else:
        console.print(f"[yellow]⚠ Không có PDF trong {pdf_dir}[/yellow]")
        console.print("[dim]→ Thêm file ADA/WHO PDF vào data/raw/guidelines/ để mở rộng knowledge base[/dim]")

    # ── Step 3: USDA CSV (optional) ───────────────────────────────────────────
    console.rule("[bold]Step 3: USDA Food Database (CSV)")
    usda_csv = RAW_DIR / "usda_fooddata.csv"
    if usda_csv.exists():
        from src.ingestion.load_csv import load_usda_csv
        usda_docs = load_usda_csv(usda_csv, max_rows=5000)
        usda_docs = enrich(usda_docs, source_name="USDA FoodData Central", doc_type="food_database")
        all_chunks.extend(usda_docs)
    else:
        console.print(f"[yellow]⚠ usda_fooddata.csv không tìm thấy — bỏ qua[/yellow]")
        console.print("[dim]→ Tải CSV tại: https://fdc.nal.usda.gov/download-foods.html[/dim]")

    # ── Step 4: Build vectorstore ─────────────────────────────────────────────
    console.rule("[bold]Step 4: Building Vector Store")

    if not all_chunks:
        console.print("[bold red]✗ Không có chunk nào để embed![/bold red]")
        console.print("[yellow]Kiểm tra lại scraper VN và thử chạy:[/yellow]")
        console.print("  python -m src.ingestion.scraper_vn")
        raise RuntimeError("all_chunks rỗng — không thể build vectorstore")

    console.print(f"[green]→[/green] Tổng cộng [bold]{len(all_chunks)}[/bold] chunks sẽ được embed")
    vs = build_vectorstore(all_chunks)

    total = vs._collection.count()
    console.print(Panel(
        f"[bold green]✓ Build thành công![/bold green]\n"
        f"Chunks đã embed: {total}\n"
        f"  • Vietnamese foods: {len(vn_chunks) if vn_json.exists() else 0}\n"
        f"  • PDF guidelines:   {len(all_chunks) - len(vn_chunks if vn_json.exists() else [])}\n"
        f"Vector store: {Path('data/embeddings/chroma_db').resolve()}",
        title="Index Ready ✓"
    ))
    return vs


def interactive_query(vectorstore):
    """Simple CLI query loop for testing."""
    from src.generation.rag_chain import rag_query
    from src.evaluation.test_cases import DEFAULT_PROFILE

    console.print(Panel(
        "[bold]Diabetes RAG Assistant[/bold]\n"
        "Type your question (or 'quit' to exit, 'vi' to switch to Vietnamese)",
        title="Ready"
    ))

    profile  = DEFAULT_PROFILE.copy()
    language = "en"
    history  = []

    while True:
        try:
            q = console.input("\n[bold green]You:[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q.lower() == "quit":
            break
        if q.lower() == "vi":
            language = "vi"
            console.print("[blue]Switched to Vietnamese mode[/blue]")
            continue
        if q.lower() == "en":
            language = "en"
            console.print("[blue]Switched to English mode[/blue]")
            continue

        result = rag_query(q, vectorstore, profile, language, history)
        console.print(f"\n[bold teal]Assistant:[/bold teal]\n{result['answer']}")
        console.print(f"\n[dim]Sources: {', '.join(result['sources'])} | Chunks: {result['chunks_used']}[/dim]")

        # Update conversation history (multi-turn)
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": result["answer"]})
        if len(history) > 10:   # keep last 5 turns
            history = history[-10:]


def main():
    parser = argparse.ArgumentParser(description="Diabetes RAG System")
    parser.add_argument("--build", action="store_true", help="Build/rebuild the index")
    parser.add_argument("--eval",  action="store_true", help="Run evaluation suite")
    parser.add_argument("--query", type=str, default=None, help="Single query mode")
    args = parser.parse_args()

    if args.build:
        vs = build_index()
    else:
        from src.retrieval.vectorstore import load_vectorstore
        vs = load_vectorstore()

    if args.eval:
        from src.evaluation.ragas_eval import run_evaluation
        from src.evaluation.test_cases import QA_TEST_CASES
        from src.generation.rag_chain import rag_query
        run_evaluation(vs, QA_TEST_CASES, rag_query, max_cases=10)
    elif args.query:
        from src.generation.rag_chain import rag_query
        from src.evaluation.test_cases import DEFAULT_PROFILE
        result = rag_query(args.query, vs, DEFAULT_PROFILE)
        console.print(result["answer"])
    else:
        interactive_query(vs)


if __name__ == "__main__":
    main()
