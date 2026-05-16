"""Test script — kiểm tra từng bước trước khi chạy python main.py --build"""
import sys, os, gc, time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
ENV_FILE = BASE_DIR / ".env"

from dotenv import load_dotenv
load_dotenv(ENV_FILE, override=True)

from rich.console import Console
from rich.table import Table
console = Console()
console.print(f"[dim]Dir: {BASE_DIR} | .env: {'✓' if ENV_FILE.exists() else '✗ NOT FOUND'}[/dim]\n")

results = []

def check(name, fn):
    try:
        fn()
        results.append((name, "✓ OK", "green"))
        console.print(f"[green]✓ PASS[/green] {name}")
    except Exception as e:
        msg = str(e).replace("\n", " ")[:200]
        results.append((name, f"✗ {msg}", "red"))
        console.print(f"[red]✗ FAIL[/red] {name}\n       [dim]{msg}[/dim]")


def _read_key(name):
    key = os.environ.get(name, "")
    if not key and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{name}="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                os.environ[name] = key
    return key


# ── 1-7: không đổi ──────────────────────────────────────────────────────────
def t1():
    from config.settings import EMBEDDING_MODEL, CHROMA_DIR, GEMINI_MODEL
    assert EMBEDDING_MODEL and CHROMA_DIR and GEMINI_MODEL
check("1. Import config/settings.py", t1)

def t2():
    key = _read_key("GEMINI_API_KEY")
    assert key, f"GEMINI_API_KEY chưa set!\nMở: {ENV_FILE}\nThêm: GEMINI_API_KEY=AIza..."
    assert key.startswith("AIza"), f"Key sai định dạng (nhận: '{key[:10]}...')\nPhải bắt đầu bằng AIza"
    console.print(f"       [dim]{key[:8]}...{key[-4:]} ✓[/dim]")
check("2. GEMINI_API_KEY hợp lệ", t2)

def t3():
    for lib in ["google.generativeai","langchain_core","chromadb",
                "sentence_transformers","bs4","pandas","rich"]:
        __import__(lib)
check("3. Các thư viện cần thiết", t3)

def t4():
    import langchain, langsmith
    console.print(f"       [dim]langchain={langchain.__version__} langsmith={langsmith.__version__}[/dim]")
check("4. langchain + langsmith tương thích", t4)

def t5():
    from src.retrieval.vectorstore import get_embedding_model
    vec = get_embedding_model().embed_query("test tiểu đường")
    assert len(vec) > 0
    console.print(f"       [dim]dim={len(vec)} ✓[/dim]")
check("5. Embedding model (BAAI/bge-m3)", t5)

def t6():
    from src.ingestion.scraper_vn import build_food_items
    items = build_food_items()
    assert len(items) >= 10
    console.print(f"       [dim]{len(items)} food items ✓[/dim]")
check("6. Scraper thực phẩm Việt Nam", t6)

def t7():
    from langchain_core.documents import Document
    from src.chunking.chunker import chunk_documents
    from src.chunking.metadata_enricher import enrich
    docs   = [Document(page_content="Người tiểu đường nên ăn GI thấp. " * 30, metadata={})]
    chunks = chunk_documents(docs, doc_type="guideline")
    chunks = enrich(chunks, source_name="Test", doc_type="guideline")
    assert chunks and chunks[0].metadata.get("topic")
    console.print(f"       [dim]{len(chunks)} chunks, topic={chunks[0].metadata['topic']} ✓[/dim]")
check("7. Chunker + metadata enricher", t7)

def t8():
    import chromadb
    from src.retrieval.vectorstore import get_embedding_model
    from langchain_core.documents import Document
    client = chromadb.EphemeralClient()
    em     = get_embedding_model()
    docs   = [Document(page_content=f"Food {i}: GI={i*10}", metadata={"topic":"nutrition","language":"vi","source":"test"})
              for i in range(1, 6)]
    texts  = [d.page_content for d in docs]
    col    = client.create_collection("test_col")
    col.add(embeddings=em.embed_documents(texts), documents=texts,
            metadatas=[d.metadata for d in docs], ids=[f"id{i}" for i in range(5)])
    assert col.count() == 5
    console.print(f"       [dim]{col.count()} vectors (in-memory) ✓[/dim]")
check("8. Build vectorstore (in-memory)", t8)

def t9():
    import chromadb
    from src.retrieval.vectorstore import get_embedding_model
    em     = get_embedding_model()
    client = chromadb.EphemeralClient()
    docs_data = [
        ("Cơm gạo lứt GI 50, tốt cho tiểu đường.", {"topic":"nutrition","language":"vi","source":"VN"}),
        ("HbA1c mục tiêu dưới 7% theo ADA.",        {"topic":"blood_sugar","language":"en","source":"ADA"}),
        ("Tập thể dục 150 phút/tuần kiểm soát đường huyết.", {"topic":"exercise","language":"en","source":"WHO"}),
    ]
    texts  = [d[0] for d in docs_data]
    metas  = [d[1] for d in docs_data]
    col    = client.create_collection("test_r")
    col.add(embeddings=em.embed_documents(texts), documents=texts,
            metadatas=metas, ids=[f"id{i}" for i in range(3)])
    result = col.query(query_embeddings=[em.embed_query("HbA1c diabetes target")], n_results=2)
    assert result["documents"][0]
    console.print(f"       [dim]Top: {result['documents'][0][0][:55]}… ✓[/dim]")
check("9. Retriever query hoạt động", t9)

def t10():
    import google.generativeai as genai
    key = _read_key("GEMINI_API_KEY")
    assert key, "GEMINI_API_KEY chưa set"
    genai.configure(api_key=key)
    model    = genai.GenerativeModel("gemini-2.0-flash")
    
    response = model.generate_content("Reply with just the word: OK")
    reply    = response.text.strip()
    assert reply
    console.print(f"       [dim]Gemini: '{reply}' ✓[/dim]")
check("10. Gemini API (LLM call)", t10)


# ── Kết quả ──────────────────────────────────────────────────────────────────
console.print()
table = Table(title="Kết quả Test Build", show_header=True, header_style="bold")
table.add_column("Test", style="bold", min_width=40)
table.add_column("Kết quả", min_width=30)

passed = 0
for name, result, color in results:
    table.add_row(name, f"[{color}]{result[:100]}[/{color}]")
    if color == "green": passed += 1

console.print(table)
console.print()
total = len(results)

if passed == total:
    console.print(f"[bold green]🎉 {total}/{total} PASS — Chạy ngay:[/bold green]")
    console.print("   [bold]python main.py --build[/bold]")
    console.print("   [bold]python main.py --eval[/bold]")
else:
    console.print(f"[bold yellow]⚠ {passed}/{total} pass — Fix lỗi đỏ:[/bold yellow]")
    for name, result, color in results:
        if color == "red":
            console.print(f"\n  [red]•[/red] [bold]{name}[/bold]")
            if "GEMINI_API_KEY" in result or "AIza" in result:
                console.print(f"    → Mở file: {ENV_FILE}")
                console.print( "    → Thêm dòng: GEMINI_API_KEY=AIzaSy...")
                console.print( "    → Lấy key miễn phí: https://aistudio.google.com/apikey")
            elif "google.generativeai" in result or "generativeai" in result:
                console.print( "    → Cài thư viện: pip install google-generativeai")
            elif "400" in result or "invalid" in result.lower():
                console.print( "    → API key sai hoặc hết quota — kiểm tra tại aistudio.google.com")
            else:
                console.print(f"    → {result[:150]}")
