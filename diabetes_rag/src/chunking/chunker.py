"""
Smart chunking for medical documents.
Different strategies per document type.
"""
from typing import List, Literal
import tiktoken
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rich.console import Console
from config.settings import CHUNK_SIZE, CHUNK_OVERLAP

console = Console()

# Token encoder (same tokenizer Claude uses)
_enc = tiktoken.get_encoding("cl100k_base")


def _token_len(text: str) -> int:
    return len(_enc.encode(text))


DocType = Literal["guideline", "research_paper", "food_database", "qa", "vn_guideline"]

# ── Per-type splitter configs ────────────────────────────────────────────────
SPLITTER_CONFIGS: dict[DocType, dict] = {
    "guideline": {          # ADA, WHO — long structured docs
        "chunk_size": CHUNK_SIZE,       # 512 tokens
        "chunk_overlap": CHUNK_OVERLAP, # 80 tokens
        "separators": ["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""],
    },
    "research_paper": {     # PubMed abstracts & full texts
        "chunk_size": 400,
        "chunk_overlap": 60,
        "separators": ["\n\n", "\n", ". ", " ", ""],
    },
    "food_database": {      # USDA / GI rows — never split these
        "chunk_size": 200,
        "chunk_overlap": 0,
        "separators": ["\n"],
    },
    "qa": {                 # FAQ pairs — keep Q+A together
        "chunk_size": 300,
        "chunk_overlap": 0,
        "separators": ["\n\n", "\n"],
    },
    "vn_guideline": {       # Vietnamese MOH documents
        "chunk_size": 450,
        "chunk_overlap": 70,
        "separators": ["\n## ", "\n### ", "\n\n", "\n", " ", ""],
    },
}


def get_splitter(doc_type: DocType) -> RecursiveCharacterTextSplitter:
    cfg = SPLITTER_CONFIGS.get(doc_type, SPLITTER_CONFIGS["guideline"])
    return RecursiveCharacterTextSplitter(
        chunk_size=cfg["chunk_size"],
        chunk_overlap=cfg["chunk_overlap"],
        length_function=_token_len,
        separators=cfg["separators"],
        keep_separator=True,
    )


def chunk_documents(
    docs: List[Document],
    doc_type: DocType = "guideline",
) -> List[Document]:
    """
    Split documents into chunks with the right strategy for their type.
    Food database rows are returned as-is (already single-item).
    """
    if doc_type == "food_database":
        console.print(f"[blue]→[/blue] Food DB: skipping split, {len(docs)} items kept as-is")
        return docs  # each CSV row is already its own document

    splitter = get_splitter(doc_type)
    chunks = splitter.split_documents(docs)

    # Filter out tiny noise chunks (< 30 tokens)
    chunks = [c for c in chunks if _token_len(c.page_content) >= 30]

    console.print(
        f"[green]✓[/green] [{doc_type}] "
        f"{len(docs)} docs → {len(chunks)} chunks "
        f"(avg {sum(_token_len(c.page_content) for c in chunks)//max(len(chunks),1)} tokens)"
    )
    return chunks


# ── Usage ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from src.ingestion.load_pdfs import load_pdf
    docs = load_pdf("data/raw/guidelines/ada_standards_2026.pdf")
    chunks = chunk_documents(docs, doc_type="guideline")
    print(f"\nSample chunk:\n{chunks[0].page_content[:400]}")
    print(f"\nMetadata: {chunks[0].metadata}")
