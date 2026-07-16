"""
================================================================
VINMEC DEEP CRAWLER
================================================================
Crawl toàn bộ bài viết tiểu đường từ Vinmec theo 2 giai đoạn:

Phase 1: Crawl trang search results → thu thập URLs bài viết
Phase 2: Crawl từng URL → lấy nội dung → lưu TXT

CÁCH DÙNG:
  # Chạy trong container:
  docker exec rag-api python scripts/crawl_vinmec.py

  # Chỉ lấy URLs (không crawl nội dung):
  docker exec rag-api python scripts/crawl_vinmec.py --urls-only

  # Giới hạn số bài:
  docker exec rag-api python scripts/crawl_vinmec.py --max-articles 50

  # Crawl + ingest luôn:
  docker exec rag-api python scripts/crawl_vinmec.py --ingest

  # Chạy ngoài máy thật (.venv):
  python scripts/crawl_vinmec.py --ingest
================================================================
"""

import sys
import time
import json
import re
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlencode
from typing import List, Dict, Optional, Set

ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))

from loguru import logger

# ── Cấu hình ─────────────────────────────────────────────────
OUTPUT_DIR   = ROOT / "data" / "pdfs"
STATE_FILE   = ROOT / ".vinmec_crawl_state.json"

# Từ khóa tìm kiếm trên Vinmec
SEARCH_QUERIES = [
    "đái tháo đường",
    "tiểu đường",
    "insulin",
    "đường huyết",
    "HbA1c",
    "metformin",
    "biến chứng tiểu đường",
    "tiểu đường thai kỳ",
    "hạ đường huyết",
    "tiểu đường type 2",
    "tiểu đường type 1",
    "chế độ ăn tiểu đường",
]

# Mapping từ khóa → category folder
QUERY_TO_CATEGORY = {
    "đái tháo đường":          "general",
    "tiểu đường":              "general",
    "insulin":                 "medication",
    "đường huyết":             "blood_glucose",
    "HbA1c":                   "blood_glucose",
    "metformin":               "medication",
    "biến chứng tiểu đường":   "general",
    "tiểu đường thai kỳ":      "complication/pregnancy",
    "hạ đường huyết":          "emergency",
    "tiểu đường type 2":       "diagnosis",
    "tiểu đường type 1":       "diagnosis",
    "chế độ ăn tiểu đường":    "diet",
}

# Mapping URL path → category (override khi biết rõ)
URL_PATH_TO_CATEGORY = {
    "tim-mach":        "cardiovascular",
    "than-tiet-nieu":  "nephropathy",
    "mat":             "retinopathy",
    "than-kinh":       "neuropathy",
    "ban-chan":         "foot_care",
    "san-phu-khoa":    "complication/pregnancy",
    "noi-tiet":        "general",
    "dinh-duong":      "diet",
    "thuoc":           "medication",
    "chan-doan":       "diagnosis",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.vinmec.com/",
}


# ── Helpers ───────────────────────────────────────────────────
def _load_state() -> Dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"crawled_urls": [], "saved_files": []}


def _save_state(state: Dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _fetch(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch URL, trả về HTML string hoặc None."""
    import urllib.request, ssl
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            raw = r.read()
        for enc in ["utf-8", "utf-8-sig", "latin-1"]:
            try:
                return raw.decode(enc)
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"Fetch lỗi {url[:60]}: {e}")
    return None


def _extract_article_urls_from_search(html: str, base_url: str) -> List[str]:
    """
    Extract URLs bài viết từ trang search results Vinmec.
    Vinmec dùng thẻ <a> với href dạng /vie/bai-viet/...
    """
    urls = []
    # Pattern 1: href="/vie/bai-viet/..."
    pattern1 = re.findall(r'href="(/vie/bai-viet/[^"?#]+)"', html)
    # Pattern 2: href="https://www.vinmec.com/vie/..."
    pattern2 = re.findall(r'href="(https://www\.vinmec\.com/vie/bai-viet/[^"?#]+)"', html)
    # Pattern 3: href="/vi/tin-tuc/..."
    pattern3 = re.findall(r'href="(/vie/tin-tuc/[^"?#]+)"', html)

    for path in pattern1 + pattern3:
        full = urljoin(base_url, path)
        if full not in urls:
            urls.append(full)
    for url in pattern2:
        if url not in urls:
            urls.append(url)
    return urls


def _get_total_pages(html: str) -> int:
    """Tìm số trang tổng từ pagination."""
    # Tìm "31-40 trên XXXX kết quả" hoặc tương tự
    m = re.search(r'(\d[\d,\.]+)\s*kết quả', html)
    if m:
        total_str = m.group(1).replace(",", "").replace(".", "")
        try:
            total = int(total_str)
            return min(total // 10 + 1, 100)  # max 100 trang để tránh vô hạn
        except Exception:
            pass
    # Tìm pagination links
    pages = re.findall(r'page=(\d+)', html)
    if pages:
        return min(max(int(p) for p in pages) + 1, 100)
    return 1


def _guess_category_from_url(url: str, default: str = "general") -> str:
    """Đoán category từ path của URL."""
    path = urlparse(url).path.lower()
    for keyword, cat in URL_PATH_TO_CATEGORY.items():
        if keyword in path:
            return cat
    return default


def _extract_article_content(html: str, url: str) -> Optional[Dict]:
    """
    Extract nội dung bài viết từ HTML trang Vinmec.
    Trả về dict {title, content, category} hoặc None.
    """
    # Extract title
    title = ""
    title_patterns = [
        r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h1>',
        r'<h1[^>]*>(.*?)</h1>',
        r'<title>(.*?)(?:\s*[-|]\s*Vinmec)?</title>',
    ]
    for pat in title_patterns:
        m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if title and len(title) > 5:
                break

    # Extract main content
    # Vinmec dùng div với class "content-detail", "article-content", "post-content"
    content_text = ""
    content_patterns = [
        r'<div[^>]*class="[^"]*content-detail[^"]*"[^>]*>(.*?)</div\s*>',
        r'<div[^>]*class="[^"]*article[^"]*content[^"]*"[^>]*>(.*?)</div\s*>',
        r'<article[^>]*>(.*?)</article>',
        r'<div[^>]*class="[^"]*post[^"]*content[^"]*"[^>]*>(.*?)</div\s*>',
        r'<div[^>]*id="content"[^>]*>(.*?)</div\s*>',
    ]

    for pat in content_patterns:
        m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
        if m:
            raw_content = m.group(1)
            # Bỏ script, style, nav
            raw_content = re.sub(r'<(script|style|nav|aside)[^>]*>.*?</\1>', '', raw_content,
                                  flags=re.DOTALL | re.IGNORECASE)
            # Bỏ HTML tags
            text = re.sub(r'<[^>]+>', ' ', raw_content)
            # Decode HTML entities
            text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
            text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
            # Clean whitespace
            text = re.sub(r'[ \t]+', ' ', text)
            text = re.sub(r'\n{3,}', '\n\n', text).strip()
            if len(text) > 200:
                content_text = text
                break

    # Fallback: lấy toàn bộ body text nếu không tìm được content
    if not content_text:
        body = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        if body:
            raw = body.group(1)
            raw = re.sub(r'<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>', '',
                          raw, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', raw)
            text = re.sub(r'[ \t]+', ' ', text)
            text = re.sub(r'\n{3,}', '\n\n', text).strip()
            if len(text) > 200:
                content_text = text

    if not content_text or not title:
        return None

    return {"title": title, "content": content_text}


# ── Phase 1: Thu thập URLs ────────────────────────────────────
def collect_article_urls(
    queries: List[str],
    max_pages_per_query: int = 10,
    delay: float = 1.5,
) -> Dict[str, List[str]]:
    """
    Crawl trang search results, trả về {category: [url1, url2, ...]}.
    """
    logger.info("📋 PHASE 1 — Thu thập URLs từ search results")
    result: Dict[str, List[str]] = {}
    seen_urls: Set[str] = set()

    for query in queries:
        category = QUERY_TO_CATEGORY.get(query, "general")
        logger.info(f"\n  🔍 Query: '{query}' → {category}")
        query_urls = []

        for page in range(1, max_pages_per_query + 1):
            # Vinmec search URL format
            params = urlencode({"q": query, "page": page}, encoding="utf-8")
            search_url = f"https://www.vinmec.com/vie/ket-qua-tim-kiem/?{params}"

            html = _fetch(search_url)
            if not html:
                logger.debug(f"    Trang {page}: không fetch được")
                break

            urls = _extract_article_urls_from_search(html, "https://www.vinmec.com")
            new_urls = [u for u in urls if u not in seen_urls]

            if not new_urls and page > 1:
                logger.debug(f"    Trang {page}: không có URL mới → dừng")
                break

            for u in new_urls:
                seen_urls.add(u)
                query_urls.append(u)

            total_pages = _get_total_pages(html)
            logger.info(f"    Trang {page}/{min(total_pages, max_pages_per_query)}: "
                        f"+{len(new_urls)} URLs (tổng: {len(query_urls)})")

            if page >= total_pages:
                break
            time.sleep(delay)

        if query_urls:
            if category not in result:
                result[category] = []
            for u in query_urls:
                if u not in result[category]:
                    result[category].append(u)

    total = sum(len(v) for v in result.values())
    logger.success(f"\n✅ Phase 1 xong: {total} URLs từ {len(result)} categories")
    for cat, urls in sorted(result.items()):
        logger.info(f"  {cat:<35}: {len(urls)} URLs")
    return result


# ── Phase 2: Crawl nội dung từng URL ─────────────────────────
def crawl_articles(
    url_map: Dict[str, List[str]],
    max_per_category: int = 50,
    delay: float = 1.5,
    skip_existing: bool = True,
) -> List[Path]:
    """
    Crawl nội dung từng URL, lưu thành TXT (UTF-8).
    """
    logger.info("\n📄 PHASE 2 — Crawl nội dung bài viết")
    state = _load_state()
    crawled_set = set(state.get("crawled_urls", []))
    saved_files = []

    for category, urls in url_map.items():
        cat_dir = OUTPUT_DIR / category
        cat_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"\n  📂 {category}: {len(urls)} URLs")
        count = 0

        for url in urls:
            if count >= max_per_category:
                logger.info(f"    Đạt giới hạn {max_per_category}")
                break
            if skip_existing and url in crawled_set:
                logger.debug(f"    ⏭ Bỏ qua (đã crawl): {url[:60]}")
                continue

            logger.info(f"    🌐 {url[:70]}")
            time.sleep(delay)

            html = _fetch(url)
            if not html:
                logger.warning(f"    ⚠ Không fetch được: {url[:60]}")
                crawled_set.add(url)
                continue

            article = _extract_article_content(html, url)
            if not article or len(article["content"]) < 300:
                logger.warning(f"    ⚠ Không extract được nội dung ({url[:60]})")
                crawled_set.add(url)
                continue

            # Tạo tên file từ URL
            url_slug = urlparse(url).path.strip("/").replace("/", "_")[:80]
            url_slug = re.sub(r'[^a-zA-Z0-9_\-]', '', url_slug)
            filename = f"vinmec__{url_slug}.txt"

            # Thêm category từ URL nếu rõ hơn
            detected_cat = _guess_category_from_url(url, category)
            if detected_cat != category:
                # Lưu vào category chính xác hơn
                actual_dir = OUTPUT_DIR / detected_cat
                actual_dir.mkdir(parents=True, exist_ok=True)
                out_path = actual_dir / filename
            else:
                out_path = cat_dir / filename

            # Tạo metadata + content
            meta = {
                "url": url,
                "title": article["title"],
                "category": detected_cat,
                "language": "vi",
                "source_name": "vinmec.com",
                "source_type": "web_article",
                "source_priority": 2,
                "verified_by_doctor": True,   # Vinmec là nguồn y tế uy tín
                "crawled_at": datetime.now().isoformat(),
                "document_title": article["title"],
            }
            file_content = (
                f"===METADATA===\n{json.dumps(meta, ensure_ascii=False, indent=2)}"
                f"\n===CONTENT===\n{article['title']}\n\n{article['content']}"
            )
            out_path.write_text(file_content, encoding="utf-8")

            crawled_set.add(url)
            saved_files.append(out_path)
            count += 1

            char_count = len(article["content"])
            logger.success(f"    ✅ {out_path.name[:50]} ({char_count:,} ký tự)")

            # Lưu state định kỳ mỗi 10 file
            if len(saved_files) % 10 == 0:
                state["crawled_urls"] = list(crawled_set)
                state["saved_files"] = [str(f) for f in saved_files]
                _save_state(state)

    # Lưu state lần cuối
    state["crawled_urls"] = list(crawled_set)
    state["saved_files"] = [str(f) for f in saved_files]
    _save_state(state)

    logger.success(f"\n✅ Phase 2 xong: {len(saved_files)} bài viết đã lưu")
    return saved_files


# ── Thêm nguồn HelloBacsi ─────────────────────────────────────
HELLOBACSI_QUERIES = {
    "https://hellobacsi.com/dai-thao-duong/":              "general",
    "https://hellobacsi.com/dai-thao-duong/an-uong-dinh-duong/": "diet",
    "https://hellobacsi.com/dai-thao-duong/bien-chung/":   "general",
    "https://hellobacsi.com/dai-thao-duong/chan-doan-benh/":"diagnosis",
    "https://hellobacsi.com/dai-thao-duong/song-chung-voi-benh/": "lifestyle",
    "https://hellobacsi.com/dai-thao-duong/tong-quan/":    "general",
}


def collect_hellobacsi_urls(max_pages: int = 5) -> Dict[str, List[str]]:
    """Crawl danh sách bài từ HelloBacsi theo category."""
    logger.info("\n📋 Thu thập URLs từ HelloBacsi...")
    result: Dict[str, List[str]] = {}
    seen: Set[str] = set()

    for base_url, category in HELLOBACSI_QUERIES.items():
        logger.info(f"  🔍 {base_url}")
        cat_urls = []
        for page in range(1, max_pages + 1):
            url = base_url if page == 1 else f"{base_url}page/{page}/"
            html = _fetch(url)
            if not html:
                break
            # HelloBacsi article links
            links = re.findall(r'href="(https://hellobacsi\.com/[^"]+/)"', html)
            new = [l for l in links if l not in seen
                   and "/dai-thao-duong/" in l
                   and l != base_url]
            if not new and page > 1:
                break
            for l in new:
                seen.add(l)
                cat_urls.append(l)
            time.sleep(1.5)

        if cat_urls:
            if category not in result:
                result[category] = []
            result[category].extend(cat_urls)
            logger.info(f"    {len(cat_urls)} URLs → {category}")

    return result


# ── Main ──────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Deep crawler cho Vinmec & HelloBacsi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python scripts/crawl_vinmec.py                    # Crawl tất cả
  python scripts/crawl_vinmec.py --max-articles 30  # Giới hạn 30 bài/category
  python scripts/crawl_vinmec.py --urls-only         # Chỉ in ra URLs
  python scripts/crawl_vinmec.py --ingest            # Crawl + ingest Qdrant
  python scripts/crawl_vinmec.py --source hellobacsi # Chỉ crawl HelloBacsi
        """
    )
    parser.add_argument("--max-articles", type=int, default=50,
                        help="Số bài tối đa mỗi category (default: 50)")
    parser.add_argument("--max-pages", type=int, default=8,
                        help="Số trang search tối đa mỗi query (default: 8)")
    parser.add_argument("--urls-only", action="store_true",
                        help="Chỉ thu thập URLs, không crawl nội dung")
    parser.add_argument("--ingest", action="store_true",
                        help="Tự động ingest vào Qdrant sau khi crawl")
    parser.add_argument("--force", action="store_true",
                        help="Crawl lại kể cả URL đã crawl")
    parser.add_argument("--source", choices=["vinmec", "hellobacsi", "all"],
                        default="all", help="Nguồn cần crawl (default: all)")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Thời gian chờ giữa các request (giây)")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("🕷  VINMEC + HELLOBACSI DEEP CRAWLER")
    logger.info("=" * 60)
    logger.info(f"  Max articles/category: {args.max_articles}")
    logger.info(f"  Max search pages:      {args.max_pages}")
    logger.info(f"  Delay:                 {args.delay}s")
    logger.info(f"  Source:                {args.source}")

    all_url_map: Dict[str, List[str]] = {}

    # Vinmec
    if args.source in ("vinmec", "all"):
        vinmec_urls = collect_article_urls(
            queries=SEARCH_QUERIES,
            max_pages_per_query=args.max_pages,
            delay=args.delay,
        )
        for cat, urls in vinmec_urls.items():
            if cat not in all_url_map:
                all_url_map[cat] = []
            all_url_map[cat].extend(urls)

    # HelloBacsi
    if args.source in ("hellobacsi", "all"):
        hb_urls = collect_hellobacsi_urls(max_pages=args.max_pages)
        for cat, urls in hb_urls.items():
            if cat not in all_url_map:
                all_url_map[cat] = []
            all_url_map[cat].extend(urls)

    # Tổng kết URLs
    total_urls = sum(len(v) for v in all_url_map.values())
    logger.info(f"\n📊 Tổng URLs thu thập: {total_urls}")
    for cat, urls in sorted(all_url_map.items()):
        logger.info(f"  {cat:<35}: {len(urls)} URLs")

    if args.urls_only:
        # In ra file để review
        urls_file = ROOT / "collected_urls.json"
        urls_file.write_text(json.dumps(all_url_map, ensure_ascii=False, indent=2),
                              encoding="utf-8")
        logger.info(f"\n💾 URLs đã lưu vào: {urls_file}")
        return

    if not all_url_map:
        logger.error("❌ Không thu thập được URL nào")
        return

    # Phase 2: Crawl nội dung
    saved = crawl_articles(
        url_map=all_url_map,
        max_per_category=args.max_articles,
        delay=args.delay,
        skip_existing=not args.force,
    )

    logger.info("\n" + "=" * 60)
    logger.info(f"✅ CRAWL XONG: {len(saved)} bài viết mới")

    # Ingest
    if args.ingest and saved:
        logger.info("\n⚙ Ingest vào Qdrant...")
        try:
            from scripts.ingest import ingest_all
            ingest_all(OUTPUT_DIR, incremental=True)
        except Exception as e:
            logger.error(f"Ingest lỗi: {e}")
            logger.info("Chạy thủ công: python scripts/ingest.py --incremental")


if __name__ == "__main__":
    main()