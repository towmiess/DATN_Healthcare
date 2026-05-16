"""Full RAG query chain: retrieve → prompt → Gemini với auto-retry."""
import time
import re
from typing import Dict, Optional, List
import google.generativeai as genai
from rich.console import Console

from config.settings import GEMINI_API_KEY, GEMINI_MODEL, MAX_TOKENS
from src.retrieval.retriever import retrieve
from src.generation.prompt_builder import build_system_prompt

console = Console()
_model = None


def get_model():
    global _model
    if _model is None:
        if not GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY chưa set!\n"
                "Mở file .env: GEMINI_API_KEY=AIza..."
            )
        genai.configure(api_key=GEMINI_API_KEY)
        _model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            generation_config=genai.GenerationConfig(
                max_output_tokens=MAX_TOKENS,
                temperature=0.3,
            )
        )
        console.print(f"[green]✓[/green] Gemini model: {GEMINI_MODEL}")
    return _model


def _parse_retry_seconds(err_msg: str) -> int:
    """Đọc số giây cần chờ từ message lỗi 429."""
    match = re.search(r"retry in (\d+)", err_msg)
    return int(match.group(1)) if match else 60


def _call_with_retry(prompt: str, max_retries: int = 3) -> str:
    """
    Gọi Gemini với tự động retry khi gặp 429 quota error.
    Đọc thời gian chờ từ chính response lỗi.
    """
    for attempt in range(1, max_retries + 1):
        try:
            model    = get_model()
            response = model.generate_content(prompt)
            return response.text

        except Exception as e:
            err = str(e)

            # ── Lỗi API key ──────────────────────────────────────
            if "API_KEY" in err or "api key" in err.lower() or "403" in err:
                raise ValueError("GEMINI_API_KEY không hợp lệ — kiểm tra file .env")

            # ── Lỗi quota 429 → chờ rồi retry ───────────────────
            if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
                wait = _parse_retry_seconds(err)

                # Nếu daily quota hết (limit: 0) → không retry được
                if "limit: 0" in err and "PerDay" in err:
                    console.print("[bold red]✗ Quota ngày đã hết![/bold red]")
                    console.print("[yellow]→ Chờ đến 0h hôm sau để reset, hoặc xem giải pháp bên dưới[/yellow]")
                    _show_quota_help()
                    raise RuntimeError("QUOTA_DAILY_EXHAUSTED")

                if attempt < max_retries:
                    console.print(f"[yellow]⚠ Quota/phút vượt — chờ {wait}s rồi thử lại "
                                  f"(lần {attempt}/{max_retries})...[/yellow]")
                    # Đếm ngược
                    for i in range(wait, 0, -5):
                        console.print(f"  [dim]Còn {i}s...[/dim]")
                        time.sleep(min(5, i))
                    continue
                else:
                    _show_quota_help()
                    raise RuntimeError(f"Vẫn lỗi 429 sau {max_retries} lần thử")

            # ── Lỗi khác ──────────────────────────────────────────
            raise RuntimeError(f"Gemini lỗi: {err[:200]}")

    raise RuntimeError("Hết số lần retry")


def _show_quota_help():
    console.print()
    console.print("[bold yellow]━━━ GIẢI PHÁP KHI HẾT QUOTA ━━━[/bold yellow]")
    console.print("[white]1.[/white] [green]Chờ đến 0h để quota reset (miễn phí)[/green]")
    console.print("[white]2.[/white] Tạo thêm API key mới tại: [link]https://aistudio.google.com/apikey[/link]")
    console.print("   Sau đó đổi GEMINI_API_KEY trong file .env")
    console.print("[white]3.[/white] Bật billing Google Cloud → quota tăng lên 1000 req/phút:")
    console.print("   [link]https://console.cloud.google.com/billing[/link]")
    console.print("[white]4.[/white] Dùng model khác trong .env:")
    console.print("   GEMINI_MODEL=gemini-1.5-flash  (quota riêng biệt)")
    console.print("[bold yellow]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold yellow]")
    console.print()


def rag_query(
    query: str,
    vectorstore,
    user_profile: Dict,
    language: str = "en",
    conversation_history: List = None,
) -> Dict:
    """Full RAG pipeline: retrieve → prompt → Gemini."""
    console.rule("[bold]RAG Query[/bold]")
    console.print(f"[blue]Q:[/blue] {query}")

    # 1 — Retrieve
    chunks = retrieve(query, vectorstore, language=language)

    # 2 — Build prompt
    system_prompt = build_system_prompt(chunks, user_profile, language)

    # 3 — Conversation history
    history_text = ""
    if conversation_history:
        for msg in conversation_history[-6:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"{role}: {msg['content']}\n\n"

    full_prompt = f"{system_prompt}\n\n{history_text}User: {query}"

    # 4 — Gọi Gemini với auto-retry
    answer = _call_with_retry(full_prompt)

    sources = list(dict.fromkeys(
        c.metadata.get("source", "Unknown") for c in chunks
    )) or ["Gemini general knowledge (no RAG context)"]

    console.print(f"[green]✓[/green] {len(answer)} chars | Sources: {sources}")

    return {
        "answer":      answer,
        "sources":     sources,
        "chunks_used": len(chunks),
        "model":       GEMINI_MODEL,
        "query":       query,
        "contexts":    [c.page_content for c in chunks],
    }