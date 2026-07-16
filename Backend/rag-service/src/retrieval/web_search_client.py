"""
src/retrieval/web_search_client.py
────────────────────────────────────
Tìm thông tin thuốc trên Internet khi OpenFDA + RxNorm không có dữ liệu
(biệt dược nước ngoài như "Atoris" — Zentiva/Slovakia, thuốc Đức/Úc/VN...).


Ưu tiên Tavily Search API (free tier ~1000 calls/tháng, thiết kế riêng cho
LLM, trả sẵn content đã trích xuất). Nếu chưa cấu hình TAVILY_API_KEY →
fallback DuckDuckGo HTML (miễn phí, không cần key, kém ổn định hơn).
"""
from __future__ import annotations

import os
import re
from typing import Optional
from urllib.parse import urlparse

import httpx
from loguru import logger

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
TAVILY_URL     = "https://api.tavily.com/search"

# Domain được cơ quan quản lý dược chính thức hoặc nguồn y tế uy tín vận
# hành — kết quả từ đây được coi là đáng tin, KHÔNG cần cảnh báo nặng.
TRUSTED_DRUG_DOMAINS = {
    "ema.europa.eu",        # European Medicines Agency
    "tga.gov.au",           # Therapeutic Goods Administration (Úc)
    "dav.gov.vn",           # Cục Quản lý Dược - Bộ Y tế Việt Nam
    "drugbank.com", "go.drugbank.com",
    "drugs.com",
    "mims.com",
    "medicines.org.uk",     # electronic Medicines Compendium (UK)
    "webmd.com",
    "thuocbietduoc.com.vn",
    "nhathuoclongchau.com.vn",
}


def _domain_of(url: str) -> str:
    try:
        d = urlparse(url).netloc.lower()
        return d[4:] if d.startswith("www.") else d
    except Exception:
        return ""


def _is_trusted(url: str) -> bool:
    domain = _domain_of(url)
    return any(domain == d or domain.endswith("." + d) for d in TRUSTED_DRUG_DOMAINS)


def _clean_snippet(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\b(webp|png|jpg|jpeg|gif)\b", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def _search_tavily(query: str, max_results: int = 3) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                TAVILY_URL,
                json={
                    "api_key":        TAVILY_API_KEY,
                    "query":          query,
                    "max_results":    max_results,
                    "search_depth":   "basic",
                    "include_answer": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        out = []
        for r in data.get("results", [])[:max_results]:
            content = _clean_snippet(r.get("content") or "")
            if len(content) > 420:
                content = content[:420].rsplit(" ", 1)[0].strip()
            if content:
                out.append({
                    "title": _clean_snippet(r.get("title") or ""),
                    "url": r.get("url", ""),
                    "content": content,
                })
        return out

    except Exception as e:
        logger.warning(f"Tavily search lỗi cho '{query}': {e}")
        return []


async def _search_duckduckgo(query: str, max_results: int = 3) -> list[dict]:
    """
    Fallback miễn phí, không cần API key — lấy snippet trực tiếp từ trang
    kết quả DuckDuckGo HTML (không crawl sâu từng trang để tránh chậm/bị
    chặn — chỉ đủ để model tham khảo, không thay được Tavily).
    """
    try:
        async with httpx.AsyncClient(
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HealthcareRAG/2.0)"},
            follow_redirects=True,
        ) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
            )
            resp.raise_for_status()
            html = resp.text

        titles   = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
        urls     = re.findall(r'class="result__a"[^>]*href="([^"]+)"', html)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)

        def _strip(s: str) -> str:
            return _clean_snippet(s)

        out = []
        for i in range(min(max_results, len(urls))):
            snippet = _strip(snippets[i]) if i < len(snippets) else ""
            if snippet:
                out.append({
                    "title": _strip(titles[i]) if i < len(titles) else "",
                    "url": urls[i],
                    "content": snippet,
                })
        return out

    except Exception as e:
        logger.warning(f"DuckDuckGo search lỗi cho '{query}': {e}")
        return []


async def search_drug_info_details(drug_name: str, max_results: int = 5) -> Optional[dict]:
    """
    Tìm thông tin thuốc trên Internet (thành phần, công dụng, liều dùng)
    khi OpenFDA + RxNorm không có dữ liệu.

    Gắn nhãn theo ĐỘ TIN CẬY CỦA NGUỒN (không theo việc thuốc có phải FDA
    hay không — thuốc EMA/TGA/Bộ Y tế VN cấp phép vẫn là thuốc hợp pháp):
      - Nguồn thuộc TRUSTED_DRUG_DOMAINS (drugs.com, EMA, TGA, MIMS...) →
        coi là đáng tin, không cần cảnh báo nặng.
      - Nguồn khác (blog, trang bán hàng, diễn đàn...) → vẫn đưa vào để
        model tham khảo, nhưng ghi rõ đây là nguồn web phổ thông, chưa
        qua kiểm chứng của cơ quan quản lý dược, để model/người dùng tự
        cân nhắc mức độ tin cậy — không phải vì thuốc đó "không chính thức".

    Trả về None nếu không tìm được gì.
    """
    query = f"{drug_name} thuốc thành phần công dụng liều dùng tác dụng phụ"

    items = (
        await _search_tavily(query, max_results)
        if TAVILY_API_KEY
        else await _search_duckduckgo(query, max_results)
    )
    if not items:
        return None

    trusted_parts, other_parts = [], []
    for it in items:
        line = f"• {it['title']}\n{it['content']}\n(Nguồn: {it['url']})"
        (trusted_parts if _is_trusted(it["url"]) else other_parts).append(line)

    blocks = ["[Thông tin thuốc tìm được từ Internet]"]
    blocks.extend(trusted_parts)
    blocks.extend(other_parts)
    return {
        "text": "\n\n".join(blocks),
        "sources": items,
    }

async def search_drug_info(drug_name: str, max_results: int = 5) -> Optional[str]:
    details = await search_drug_info_details(drug_name, max_results=max_results)
    return details["text"] if details else None
