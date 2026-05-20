"""
================================================================
BƯỚC 1: CRAWLER — Thu Thập Tài Liệu Y Khoa Về Tiểu Đường
================================================================

TẠI SAO CẦN BƯỚC NÀY?
  LLM (Claude, GPT...) không có kiến thức y khoa cập nhật và
  có thể "hallucinate" — bịa ra thông tin sai. Bước này thu
  thập tài liệu từ các nguồn uy tín để xây dựng "kho tri thức"
  cho hệ thống RAG.

LUỒNG HOẠT ĐỘNG:
  URL nguồn uy tín
      │
      ▼
  HTTP Request (giả lập trình duyệt)
      │
      ▼
  BeautifulSoup parse HTML
      │
      ▼
  Trích xuất nội dung chính (bỏ quảng cáo, menu)
      │
      ▼
  Lưu .txt vào data/raw/

CÁCH CHẠY:
  python src/crawler/medical_crawler.py
================================================================
"""

import os
import time
import json
import hashlib
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from loguru import logger
from tqdm import tqdm


# ── Thư mục lưu tài liệu thô ────────────────────────────────
RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ── Headers giả lập Chrome để tránh bị chặn ─────────────────
# Nhiều website chặn request từ bot; ta giả vờ là trình duyệt thật
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}


@dataclass
class MedicalSource:
    """
    Mô tả một nguồn tài liệu y khoa cần crawl.

    Attributes:
        name        : Tên định danh (dùng làm tên file)
        url         : Địa chỉ trang web
        category    : Nhóm chủ đề (tieu_duong / che_do_an / dieu_tri...)
        selector    : CSS selector trỏ đến vùng nội dung chính
                      → Mỗi website có cấu trúc HTML khác nhau,
                        nên cần chỉ định selector riêng
        language    : 'vi' hoặc 'en'
    """
    name: str
    url: str
    category: str
    selector: str = "article"
    language: str = "vi"


# ================================================================
# DANH SÁCH NGUỒN TÀI LIỆU UY TÍN VỀ TIỂU ĐƯỜNG
# Thêm URL mới tại đây để mở rộng kho tri thức
# ================================================================
MEDICAL_SOURCES: List[MedicalSource] = [

    # ── TIỂU ĐƯỜNG — KIẾN THỨC CƠ BẢN ──────────────────────
    MedicalSource(
        name="vinmec_tieu_duong_type2",
        url="https://www.vinmec.com/vi/benh/tieu-duong-typ-2-3404/",
        category="tieu_duong_type2",
        selector=".detail-content",
        language="vi",
    ),
    MedicalSource(
        name="vinmec_bien_chung_tieu_duong",
        url="https://www.vinmec.com/vi/tin-tuc/thong-tin-suc-khoe/bien-chung-cua-benh-tieu-duong-va-cach-phong-ngua/",
        category="tieu_duong_type2",
        selector=".detail-content",
        language="vi",
    ),
    MedicalSource(
        name="hellobacsi_tieu_duong_type2",
        url="https://hellobacsi.com/benh-tieu-duong/tieu-duong-type-2/benh-tieu-duong-type-2/",
        category="tieu_duong_type2",
        selector=".single-post__content",
        language="vi",
    ),
    MedicalSource(
        name="bookingcare_tieu_duong",
        url="https://bookingcare.vn/cam-nang/benh-tieu-duong-la-gi-p1150.html",
        category="tieu_duong_type2",
        selector=".content-detail",
        language="vi",
    ),

    # ── CHỈ SỐ ĐƯỜNG HUYẾT ──────────────────────────────────
    MedicalSource(
        name="vinmec_duong_huyet",
        url="https://www.vinmec.com/vi/tin-tuc/thong-tin-suc-khoe/chi-so-duong-huyet-binh-thuong-la-bao-nhieu/",
        category="chi_so_duong_huyet",
        selector=".detail-content",
        language="vi",
    ),
    MedicalSource(
        name="hellobacsi_hba1c",
        url="https://hellobacsi.com/benh-tieu-duong/xet-nghiem-tieu-duong/xet-nghiem-hba1c/",
        category="chi_so_duong_huyet",
        selector=".single-post__content",
        language="vi",
    ),

    # ── CHẾ ĐỘ ĂN KIÊNG ─────────────────────────────────────
    MedicalSource(
        name="vinmec_che_do_an",
        url="https://www.vinmec.com/vi/tin-tuc/thong-tin-suc-khoe/thuc-pham-tot-cho-nguoi-benh-tieu-duong/",
        category="che_do_an",
        selector=".detail-content",
        language="vi",
    ),
    MedicalSource(
        name="hellobacsi_thuc_pham_nen_an",
        url="https://hellobacsi.com/benh-tieu-duong/song-chung-voi-benh-tieu-duong/che-do-an-cho-nguoi-tieu-duong/",
        category="che_do_an",
        selector=".single-post__content",
        language="vi",
    ),
    MedicalSource(
        name="bookingcare_che_do_an",
        url="https://bookingcare.vn/cam-nang/che-do-an-cho-nguoi-bi-tieu-duong-p3047.html",
        category="che_do_an",
        selector=".content-detail",
        language="vi",
    ),

    # ── INSULIN & ĐIỀU TRỊ ──────────────────────────────────
    MedicalSource(
        name="vinmec_insulin",
        url="https://www.vinmec.com/vi/tin-tuc/thong-tin-suc-khoe/insulin-trong-dieu-tri-benh-tieu-duong/",
        category="dieu_tri",
        selector=".detail-content",
        language="vi",
    ),
    MedicalSource(
        name="hellobacsi_metformin",
        url="https://hellobacsi.com/benh-tieu-duong/dieu-tri-tieu-duong/thuoc-dieu-tri-tieu-duong-type-2/",
        category="dieu_tri",
        selector=".single-post__content",
        language="vi",
    ),

    # ── THỂ DỤC & LỐI SỐNG ──────────────────────────────────
    MedicalSource(
        name="vinmec_van_dong",
        url="https://www.vinmec.com/vi/tin-tuc/thong-tin-suc-khoe/tap-the-duc-cho-nguoi-benh-tieu-duong/",
        category="the_duc_loi_song",
        selector=".detail-content",
        language="vi",
    ),

    # ── NGUỒN TIẾNG ANH (WHO, Mayo) ─────────────────────────
    MedicalSource(
        name="who_diabetes_facts",
        url="https://www.who.int/news-room/fact-sheets/detail/diabetes",
        category="tieu_duong_type2",
        selector=".sf-detail-body-wrapper",
        language="en",
    ),
    MedicalSource(
        name="mayo_diabetes_diet",
        url="https://www.mayoclinic.org/diseases-conditions/diabetes/in-depth/diabetes-diet/art-20044295",
        category="che_do_an",
        selector=".content",
        language="en",
    ),
]


class HealthcareCrawler:
    """
    Crawler chuyên thu thập tài liệu y khoa.

    Tính năng:
    ✅ Retry tự động (3 lần) nếu lỗi mạng
    ✅ Delay giữa các request (tránh bị ban IP)
    ✅ Nhiều selector fallback nếu cấu trúc HTML thay đổi
    ✅ Lưu metadata kèm theo (URL gốc, ngày crawl, category)
    ✅ Bỏ qua file đã crawl rồi (không crawl lại)
    """

    # Các selector fallback phổ biến nếu selector chính không có
    FALLBACK_SELECTORS = [
        "main", "article", "[role='main']",
        ".post-content", ".entry-content",
        ".article-body", ".page-content", "#content",
    ]

    def __init__(self, output_dir: Path = RAW_DIR, delay: float = 2.5):
        """
        Args:
            output_dir: Thư mục lưu file .txt kết quả
            delay: Giây chờ giữa mỗi request (lịch sự với server)
        """
        self.output_dir = output_dir
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.results = []  # Lưu kết quả để export metadata

    # ── PRIVATE METHODS ──────────────────────────────────────

    def _fetch_html(self, url: str, retries: int = 3) -> Optional[str]:
        """
        Tải HTML từ URL.

        Dùng exponential backoff: lần 1 chờ 2.5s, lần 2 chờ 5s, lần 3 chờ 7.5s
        → Tránh làm quá tải server và tránh bị ban IP.
        """
        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=20)
                resp.raise_for_status()  # Raise exception nếu HTTP 4xx/5xx
                # Tự detect encoding (UTF-8, ISO-8859-1...) để hiển thị đúng tiếng Việt
                resp.encoding = resp.apparent_encoding
                return resp.text

            except requests.RequestException as e:
                wait = self.delay * (attempt + 1)
                logger.warning(f"  ⚠ Thử {attempt+1}/{retries} thất bại: {e}")
                if attempt < retries - 1:
                    logger.info(f"  ⏳ Chờ {wait}s rồi thử lại...")
                    time.sleep(wait)

        logger.error(f"  ✗ Không thể tải: {url}")
        return None

    def _extract_text(self, html: str, source: MedicalSource) -> Optional[str]:
        """
        Parse HTML → text thuần, loại bỏ nhiễu.

        Quy trình:
        1. Parse HTML bằng lxml (nhanh và chuẩn)
        2. Xóa thẻ gây nhiễu: script, style, nav, footer, quảng cáo
        3. Tìm vùng nội dung chính theo selector
        4. Fallback sang các selector phổ biến nếu không tìm được
        5. Lấy text và làm sạch khoảng trắng thừa
        """
        soup = BeautifulSoup(html, "lxml")

        # Bước 2: Xóa noise — quảng cáo, menu, script...
        noise_selectors = [
            "script", "style", "nav", "footer", "header",
            "aside", "iframe", "noscript",
            ".advertisement", ".ads", ".social-share",
            ".related-posts", ".sidebar", ".cookie-notice",
            "[class*='banner']", "[class*='popup']",
        ]
        for sel in noise_selectors:
            for tag in soup.select(sel):
                tag.decompose()  # Xóa hoàn toàn khỏi DOM

        # Bước 3: Tìm vùng nội dung chính
        content_area = soup.select_one(source.selector)

        # Bước 4: Fallback nếu không tìm được selector chính
        if not content_area:
            logger.debug(f"  Selector '{source.selector}' không tìm thấy, thử fallback...")
            for fallback in self.FALLBACK_SELECTORS:
                content_area = soup.select_one(fallback)
                if content_area:
                    logger.debug(f"  ✓ Dùng fallback: '{fallback}'")
                    break

        # Bước 5: Trích xuất và làm sạch text
        if content_area:
            # get_text(separator='\n') giữ lại cấu trúc đoạn văn
            raw_text = content_area.get_text(separator="\n")
        else:
            # Worst case: lấy toàn bộ body
            logger.warning(f"  ⚠ Không tìm được vùng content, lấy toàn body")
            raw_text = soup.get_text(separator="\n")

        # Làm sạch: bỏ dòng trống thừa, strip khoảng trắng
        lines = [line.strip() for line in raw_text.splitlines()]
        clean_lines = [l for l in lines if l]  # Bỏ dòng rỗng
        return "\n".join(clean_lines)

    def _save_text(self, source: MedicalSource, text: str, char_count: int):
        """
        Lưu text kèm metadata vào file .txt.

        Format file:
        ===METADATA===
        URL: ...
        CATEGORY: ...
        ...
        ===CONTENT===
        (nội dung tài liệu)
        """
        filename = f"{source.category}__{source.name}.txt"
        filepath = self.output_dir / filename

        from datetime import datetime
        metadata = {
            "source_name": source.name,
            "url": source.url,
            "category": source.category,
            "language": source.language,
            "crawled_at": datetime.now().isoformat(),
            "char_count": char_count,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("===METADATA===\n")
            f.write(json.dumps(metadata, ensure_ascii=False, indent=2))
            f.write("\n===CONTENT===\n")
            f.write(text)

        return filepath

    # ── PUBLIC METHODS ───────────────────────────────────────

    def crawl_source(self, source: MedicalSource) -> Optional[dict]:
        """
        Crawl một nguồn tài liệu.

        Returns:
            Dict kết quả hoặc None nếu thất bại
        """
        # Kiểm tra đã crawl chưa → không crawl lại
        filename = f"{source.category}__{source.name}.txt"
        filepath = self.output_dir / filename
        if filepath.exists():
            logger.info(f"  ⏭ Đã có: {filename} (bỏ qua)")
            return {"status": "skipped", "file": str(filepath)}

        logger.info(f"  🌐 Đang crawl: {source.name}")
        logger.info(f"     URL: {source.url}")

        # Tải HTML
        html = self._fetch_html(source.url)
        if not html:
            return {"status": "failed", "source": source.name}

        # Trích xuất text
        text = self._extract_text(html, source)
        if not text or len(text) < 200:
            logger.warning(f"  ⚠ Nội dung quá ngắn ({len(text) if text else 0} ký tự), bỏ qua")
            return {"status": "too_short", "source": source.name}

        # Lưu file
        saved_path = self._save_text(source, text, len(text))
        logger.success(f"  ✅ Đã lưu: {saved_path.name} ({len(text):,} ký tự)")

        return {
            "status": "success",
            "source": source.name,
            "category": source.category,
            "chars": len(text),
            "file": str(saved_path),
        }

    def crawl_all(self, sources: List[MedicalSource] = None) -> List[dict]:
        """
        Crawl toàn bộ danh sách nguồn.

        Args:
            sources: Danh sách nguồn (mặc định: MEDICAL_SOURCES)

        Returns:
            Danh sách kết quả mỗi nguồn
        """
        sources = sources or MEDICAL_SOURCES
        logger.info(f"🚀 Bắt đầu crawl {len(sources)} nguồn tài liệu...")

        results = []
        for i, source in enumerate(tqdm(sources, desc="Crawling"), 1):
            logger.info(f"\n[{i}/{len(sources)}] {source.name}")
            result = self.crawl_source(source)
            if result:
                results.append(result)

            # Delay giữa các request (trừ request cuối)
            if i < len(sources):
                time.sleep(self.delay)

        # Thống kê kết quả
        success = sum(1 for r in results if r.get("status") == "success")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        failed  = sum(1 for r in results if r.get("status") == "failed")

        logger.info(f"\n{'='*50}")
        logger.info(f"📊 KẾT QUẢ CRAWL:")
        logger.info(f"   ✅ Thành công: {success}")
        logger.info(f"   ⏭ Đã có sẵn: {skipped}")
        logger.info(f"   ✗ Thất bại  : {failed}")
        logger.info(f"{'='*50}")

        # Lưu metadata tổng hợp
        meta_path = self.output_dir / "crawl_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"📋 Metadata lưu tại: {meta_path}")

        return results


# ── CHẠY TRỰC TIẾP ──────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🏥 HEALTHCARE CRAWLER — Thu Thập Tài Liệu Y Khoa")
    logger.info("=" * 60)

    crawler = HealthcareCrawler(delay=2.0)
    results = crawler.crawl_all()

    success_count = sum(1 for r in results if r.get("status") == "success")
    if success_count > 0:
        logger.success(f"\n✅ Crawl xong! Đã thu thập {success_count} tài liệu.")
        logger.info("📁 Tài liệu lưu tại: data/raw/")
        logger.info("▶  Bước tiếp theo: python src/preprocessor/pdf_builder.py")
    else:
        logger.warning("\n⚠ Không crawl được tài liệu nào. Kiểm tra kết nối mạng.")
