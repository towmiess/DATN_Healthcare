"""Load PDF documents (ADA guidelines, WHO, PubMed papers)."""
from pathlib import Path
from typing import List
import fitz  # pymupdf
from langchain_core.documents import Document
from rich.console import Console

console = Console()


def load_pdf(pdf_path: str | Path) -> List[Document]:
    """
    Load a single PDF → list of LangChain Documents (1 doc per page).
    Preserves page numbers and section headers in metadata.
    """
    pdf_path = Path(pdf_path)
    docs: List[Document] = []
    pdf = fitz.open(str(pdf_path))

    for page_num, page in enumerate(pdf, start=1):
        text = page.get_text("text").strip()
        if not text or len(text) < 50:   # skip blank/header-only pages
            continue
        docs.append(Document(
            page_content=text,
            metadata={
                "source_file": pdf_path.name,
                "page": page_num,
                "total_pages": len(pdf),
                "file_path": str(pdf_path),
            }
        ))

    console.print(f"[green]✓[/green] Loaded [bold]{pdf_path.name}[/bold] "
                  f"— {len(docs)} pages")
    return docs


def load_pdf_folder(folder: str | Path, glob: str = "**/*.pdf") -> List[Document]:
    """Load all PDFs from a folder recursively."""
    folder = Path(folder)
    all_docs: List[Document] = []
    pdf_files = list(folder.glob(glob))

    if not pdf_files:
        console.print(f"[yellow]⚠ No PDFs found in {folder}[/yellow]")
        return []

    console.print(f"[blue]→[/blue] Found {len(pdf_files)} PDFs in {folder}")
    for pdf_file in pdf_files:
        docs = load_pdf(pdf_file)
        all_docs.extend(docs)

    console.print(f"[green]✓[/green] Total pages loaded: {len(all_docs)}")
    return all_docs


# ── Usage example ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    docs = load_pdf_folder("data/raw/guidelines/")
    print(f"Loaded {len(docs)} pages from all guidelines")
    print(docs[0].page_content[:300])
