"""
================================================================
CRAWLER — Tự Động Crawl Dữ Liệu Y Tế Theo Danh Mục
================================================================

Crawl tài liệu từ các nguồn y tế uy tín và lưu thành PDF/TXT
vào đúng folder tương ứng trong data/pdfs/.

Nguồn crawl:
  - PubMed / PMC (miễn phí, bài báo khoa học)
  - WHO / CDC (tài liệu hướng dẫn)
  - ADA (American Diabetes Association)
  - Vinmec / HelloBacsi (tiếng Việt)

CÁC DÙNG:
  # Crawl tất cả danh mục:
  python scripts/crawler.py

  # Crawl một danh mục cụ thể:
  python scripts/crawler.py --category cardiovascular

  # Chỉ xem danh sách URL sẽ crawl (dry run):
  python scripts/crawler.py --dry-run

  # Crawl + ingest luôn vào Qdrant:
  python scripts/crawler.py --ingest

  # Giới hạn số trang mỗi danh mục:
  python scripts/crawler.py --max-per-category 5
================================================================
"""

import sys
import argparse
import time
import hashlib
import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))

from loguru import logger

# ── Cấu hình thư mục ─────────────────────────────────────────
PDF_BASE_DIR = ROOT / "data" / "pdfs"
RAW_DIR      = ROOT / "data" / "raw"
STATE_FILE   = ROOT / ".crawler_state.json"

# ── Nguồn crawl theo danh mục ────────────────────────────────
# Mỗi source: {url, title, category, language, source_type, priority}
CRAWL_SOURCES: Dict[str, List[Dict]] = {

    # ── Blood Glucose ────────────────────────────────────────
    "blood_glucose": [
        {
            "url": "https://www.cdc.gov/diabetes/diabetes-testing/index.html",
            "title": "Diabetes Testing - CDC",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.niddk.nih.gov/health-information/diabetes/overview/managing-diabetes/blood-glucose",
            "title": "Managing Blood Glucose - NIDDK",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.hellobacsi.com/dai-thao-duong/song-chung-voi-benh/kiem-tra-duong-huyet/",
            "title": "Kiểm Tra Đường Huyết - HelloBacsi",
            "language": "vi", "priority": 2,
        },
        {
            "url": "https://www.vinmec.com/vi/tieu-hoa-gan-mat/thong-tin-suc-khoe/chi-so-duong-huyet-bao-nhieu-la-binh-thuong/",
            "title": "Chỉ Số Đường Huyết Bình Thường - Vinmec",
            "language": "vi", "priority": 2,
        },
    ],

    # ── Diagnosis ────────────────────────────────────────────
    "diagnosis": [
        {
            "url": "https://www.cdc.gov/diabetes/signs-symptoms/index.html",
            "title": "Diabetes Signs & Symptoms - CDC",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.diabetes.org/diabetes/a1c",
            "title": "A1C and Diagnosis - ADA",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.hellobacsi.com/dai-thao-duong/chan-doan-benh/chan-doan-tieu-duong-type-2/",
            "title": "Chẩn Đoán Tiểu Đường Type 2 - HelloBacsi",
            "language": "vi", "priority": 2,
        },
        {
            "url": "https://www.vinmec.com/vi/tieu-hoa-gan-mat/thong-tin-suc-khoe/tieu-chuan-chan-doan-dai-thao-duong/",
            "title": "Tiêu Chuẩn Chẩn Đoán Đái Tháo Đường - Vinmec",
            "language": "vi", "priority": 2,
        },
        {
            "url": "https://www.niddk.nih.gov/health-information/diabetes/overview/what-is-diabetes",
            "title": "What Is Diabetes - NIDDK",
            "language": "en", "priority": 1,
        },
    ],

    # ── Diet ─────────────────────────────────────────────────
    "diet": [
        {
            "url": "https://www.diabetes.org/healthy-living/recipes-nutrition/eating-well",
            "title": "Eating Well with Diabetes - ADA",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.niddk.nih.gov/health-information/diabetes/overview/diet-eating-physical-activity",
            "title": "Diabetes Diet and Eating - NIDDK",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.hellobacsi.com/dai-thao-duong/an-uong-dinh-duong/",
            "title": "Ăn Uống Dinh Dưỡng Tiểu Đường - HelloBacsi",
            "language": "vi", "priority": 2,
        },
        {
            "url": "https://www.vinmec.com/vi/tieu-hoa-gan-mat/thong-tin-suc-khoe/che-do-an-cho-nguoi-benh-dai-thao-duong/",
            "title": "Chế Độ Ăn Cho Người Đái Tháo Đường - Vinmec",
            "language": "vi", "priority": 2,
        },
    ],

    # ── Emergency ────────────────────────────────────────────
    "emergency": [
        {
            "url": "https://www.cdc.gov/diabetes/treatment/low-blood-sugar.html",
            "title": "Low Blood Sugar Treatment - CDC",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/low-blood-glucose-hypoglycemia",
            "title": "Hypoglycemia - NIDDK",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.hellobacsi.com/dai-thao-duong/bien-chung/ha-duong-huyet-nguy-hiem/",
            "title": "Hạ Đường Huyết Nguy Hiểm - HelloBacsi",
            "language": "vi", "priority": 2,
        },
        {
            "url": "https://www.vinmec.com/vi/tieu-hoa-gan-mat/thong-tin-suc-khoe/cach-xu-tri-khi-bi-ha-duong-huyet/",
            "title": "Cách Xử Trí Hạ Đường Huyết - Vinmec",
            "language": "vi", "priority": 2,
        },
    ],

    # ── Diagnosis ────────────────────────────────────────────
    "diagnosis": [
        {
            "url": "https://www.cdc.gov/diabetes/signs-symptoms/index.html",
            "title": "Diabetes Signs & Symptoms - CDC",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.diabetes.org/diabetes/a1c",
            "title": "A1C and Diagnosis - ADA",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.hellobacsi.com/dai-thao-duong/chan-doan-benh/chan-doan-tieu-duong-type-2/",
            "title": "Chẩn Đoán Tiểu Đường Type 2 - HelloBacsi",
            "language": "vi", "priority": 2,
        },
        {
            "url": "https://www.vinmec.com/vi/tieu-hoa-gan-mat/thong-tin-suc-khoe/tieu-chuan-chan-doan-dai-thao-duong/",
            "title": "Tiêu Chuẩn Chẩn Đoán Đái Tháo Đường - Vinmec",
            "language": "vi", "priority": 2,
        },
        {
            "url": "https://www.niddk.nih.gov/health-information/diabetes/overview/what-is-diabetes",
            "title": "What Is Diabetes - NIDDK",
            "language": "en", "priority": 1,
        },
    ],

    # ── Diet ─────────────────────────────────────────────────
    "diet": [
        {
            "url": "https://www.diabetes.org/healthy-living/recipes-nutrition/eating-well",
            "title": "Eating Well with Diabetes - ADA",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.niddk.nih.gov/health-information/diabetes/overview/diet-eating-physical-activity",
            "title": "Diabetes Diet and Eating - NIDDK",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.hellobacsi.com/dai-thao-duong/an-uong-dinh-duong/",
            "title": "Ăn Uống Dinh Dưỡng Tiểu Đường - HelloBacsi",
            "language": "vi", "priority": 2,
        },
        {
            "url": "https://www.vinmec.com/vi/tieu-hoa-gan-mat/thong-tin-suc-khoe/che-do-an-cho-nguoi-benh-dai-thao-duong/",
            "title": "Chế Độ Ăn Cho Người Đái Tháo Đường - Vinmec",
            "language": "vi", "priority": 2,
        },
    ],

    # ── General ──────────────────────────────────────────────
    "general": [
        {
            "url": "https://www.cdc.gov/diabetes/basics/index.html",
            "title": "Diabetes Basics - CDC",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.who.int/news-room/fact-sheets/detail/diabetes",
            "title": "Diabetes Fact Sheet - WHO",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.vinmec.com/vi/tieu-hoa-gan-mat/thong-tin-suc-khoe/nguyen-nhan-gay-benh-tieu-duong/",
            "title": "Nguyên Nhân Gây Bệnh Tiểu Đường - Vinmec",
            "language": "vi", "priority": 2,
        },
        {
            "url": "https://www.hellobacsi.com/dai-thao-duong/tong-quan/tieu-duong-la-gi/",
            "title": "Tiểu Đường Là Gì - HelloBacsi",
            "language": "vi", "priority": 2,
        },
    ],

    # ── Lifestyle ────────────────────────────────────────────
    "lifestyle": [
        {
            "url": "https://www.cdc.gov/diabetes/living-with/index.html",
            "title": "Living with Diabetes - CDC",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.diabetes.org/healthy-living/fitness",
            "title": "Fitness for Diabetes - ADA",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.hellobacsi.com/dai-thao-duong/song-chung-voi-benh/",
            "title": "Sống Chung Với Tiểu Đường - HelloBacsi",
            "language": "vi", "priority": 2,
        },
        {
            "url": "https://www.vinmec.com/vi/tieu-hoa-gan-mat/thong-tin-suc-khoe/tap-the-duc-cho-nguoi-benh-tieu-duong/",
            "title": "Tập Thể Dục Cho Người Tiểu Đường - Vinmec",
            "language": "vi", "priority": 2,
        },
    ],

    # ── Medication ───────────────────────────────────────────
    "medication": [
        {
            "url": "https://www.niddk.nih.gov/health-information/diabetes/overview/insulin-medicines-treatments",
            "title": "Diabetes Medicines - NIDDK",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.diabetes.org/healthy-living/medication-treatments/oral-medication",
            "title": "Oral Medications - ADA",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.hellobacsi.com/thuoc/metformin/",
            "title": "Thuốc Metformin - HelloBacsi",
            "language": "vi", "priority": 2,
        },
        {
            "url": "https://www.vinmec.com/vi/tieu-hoa-gan-mat/thong-tin-suc-khoe/dieu-tri-dai-thao-duong-type-2-bang-thuoc/",
            "title": "Điều Trị Đái Tháo Đường Type 2 Bằng Thuốc - Vinmec",
            "language": "vi", "priority": 2,
        },
    ],

    # ── Complications → Cardiovascular ───────────────────────
    "complication/cardiovascular": [
        {
            "url": "https://www.heart.org/en/health-topics/diabetes/diabetes-complications-and-risks",
            "title": "Diabetes and Heart Disease - AHA",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/heart-disease-stroke",
            "title": "Heart Disease and Diabetes - NIDDK",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.vinmec.com/vi/tieu-hoa-gan-mat/thong-tin-suc-khoe/bien-chung-tim-mach-o-nguoi-benh-tieu-duong/",
            "title": "Biến Chứng Tim Mạch Ở Người Tiểu Đường - Vinmec",
            "language": "vi", "priority": 2,
        },
        {
            "url": "https://www.hellobacsi.com/dai-thao-duong/bien-chung/bien-chung-tim-mach/",
            "title": "Biến Chứng Tim Mạch - HelloBacsi",
            "language": "vi", "priority": 2,
        },
    ],

    # ── Complications → Nephropathy ──────────────────────────
    "complication/nephropathy": [
        {
            "url": "https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/diabetic-kidney-disease",
            "title": "Diabetic Kidney Disease - NIDDK",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.kidney.org/diabetes",
            "title": "Diabetes and Kidney Disease - NKF",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.vinmec.com/vi/tieu-hoa-gan-mat/thong-tin-suc-khoe/bien-chung-than-do-dai-thao-duong/",
            "title": "Biến Chứng Thận Do Đái Tháo Đường - Vinmec",
            "language": "vi", "priority": 2,
        },
    ],

    # ── Complications → Neuropathy ───────────────────────────
    "complication/neuropathy": [
        {
            "url": "https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/nerve-damage-diabetic-neuropathies",
            "title": "Diabetic Neuropathy - NIDDK",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.diabetes.org/diabetes/complications/neuropathy",
            "title": "Neuropathy - ADA",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.vinmec.com/vi/tieu-hoa-gan-mat/thong-tin-suc-khoe/bien-chung-than-kinh-ngoai-vi-do-dai-thao-duong/",
            "title": "Biến Chứng Thần Kinh Ngoại Vi - Vinmec",
            "language": "vi", "priority": 2,
        },
    ],

    # ── Complications → Pregnancy ────────────────────────────
    "complication/pregnancy": [
        {
            "url": "https://www.niddk.nih.gov/health-information/diabetes/overview/what-is-diabetes/gestational",
            "title": "Gestational Diabetes - NIDDK",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.cdc.gov/diabetes/risk-factors/gestational-diabetes.html",
            "title": "Gestational Diabetes - CDC",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.diabetes.org/diabetes/gestational-diabetes",
            "title": "Gestational Diabetes - ADA",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://medlatec.vn/tin-tuc/tieu-duong-thai-ky-nen-an-gi-vao-bua-sang-bua-trua-va-toi-de-thai-ky-khoe-manh",
            "title": "Tiểu Đường Thai Kỳ - Medlatec",
            "language": "vi", "priority": 1,
        },
        {
            "url": "https://chanhtuoi.com/thuc-don-cho-ba-bau-bi-tieu-duong-thai-ky-p10391.html",
            "title": "Thực Đơn Cho Bà Bầu Bị Tiểu Đường Thai Kỳ - Chanh Tuổi",
            "language": "vi", "priority": 1,
        },
        {
            "url": "https://www.vinmec.com/vie/bai-viet/thuc-don-goi-y-cho-ba-bau-mac-tieu-duong-thai-ky-vi",
            "title": "Thực Đơn Gợi Ý Cho Bà Bầu Mắc Tiểu Đường Thai Kỳ - Vinmec",
            "language": "vi", "priority": 1,
        },
        {
            "url": "https://nhathuoclongchau.com.vn/bai-viet/diem-danh-12-mon-an-vat-cho-ba-bau-tieu-duong-thai-ky-bo-duong-nhat.html",
            "title": "12 Món Ăn Vặt Cho Bà Bầu Tiểu Đường Thai Kỳ - Long Châu",
            "language": "vi", "priority": 1,
        },
        {
            "url": "https://www.mediplus.vn/san-khoa/tieu-duong-thai-ky-nen-an-gi.html",
            "title": "Tiểu Đường Thai Kỳ Nên Ăn Gì - Mediplus",
            "language": "vi", "priority": 1,
        },
        {
            "url": "https://www.avakids.com/me-va-be/goi-y-thuc-don-cho-ba-bau-bi-tieu-duong-thai-ky-1468580",
            "title": "Gợi Ý Thực Đơn Cho Bà Bầu Bị Tiểu Đường Thai Kỳ - AvaKids",
            "language": "vi", "priority": 1,
        },
    ],
    
    # ── Complications → Retinopathy ──────────────────────────
    "complication/retinopathy": [
        {
            "url": "https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/diabetic-eye-disease",
            "title": "Diabetic Eye Disease - NIDDK",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.nei.nih.gov/learn-about-eye-health/eye-conditions-and-diseases/diabetic-retinopathy",
            "title": "Diabetic Retinopathy - NEI",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.vinmec.com/vi/tieu-hoa-gan-mat/thong-tin-suc-khoe/bien-chung-mat-do-dai-thao-duong/",
            "title": "Biến Chứng Mắt Do Đái Tháo Đường - Vinmec",
            "language": "vi", "priority": 2,
        },
    ],

    # ── Complications → Foot Care ────────────────────────────
    "complication/foot_care": [
        {
            "url": "https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/foot-problems",
            "title": "Diabetic Foot Problems - NIDDK",
            "language": "en", "priority": 1,
        },
        {
            "url": "https://www.diabetes.org/diabetes/complications/foot-complications",
            "title": "Foot Complications - ADA",
            "language": "en", "priority": 1,
        },
        
        {
            "url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/bien-chung-tieu-duong/bien-chung-te-bi-chan-tay-o-nguoi-dai-thao-duong/",
            "title": "Biến Chứng Tê Bì Chân Tay Ở Người Đái Tháo Đường - HelloBacsi",
            "language": "vi", "priority": 1,
        },
        {
            "url": "https://www.vinmec.com/vi/tieu-hoa-gan-mat/thong-tin-suc-khoe/cham-soc-ban-chan-cho-nguoi-benh-dai-thao-duong/",
            "title": "Chăm Sóc Bàn Chân Tiểu Đường - Vinmec",
            "language": "vi", "priority": 1,
        },
        {
            "url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/bien-chung-tieu-duong/cham-soc-ban-chan-tieu-duong/",
            "title": "Chăm Sóc Bàn Chân Tiểu Đường - HelloBacsi",
            "language": "vi", "priority": 1,
        },
        {
            "url": "https://www.hellobacsi.com/dai-thao-duong/bien-chung/bien-chung-ban-chan/",
            "title": "Biến Chứng Bàn Chân Tiểu Đường - HelloBacsi",
            "language": "vi", "priority": 2,
        },
    ],
}


def _load_state() -> Dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: Dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _url_to_filename(url: str, category: str) -> str:
    """Chuyển URL thành tên file an toàn."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "").replace(".", "_")
    path = parsed.path.strip("/").replace("/", "_")[:60]
    # lấy tên miền làm prefix
    cat_clean = category.replace("/", "_")
    name = f"{cat_clean}__{domain}__{path}"
    # làm sạch ký tự đặc biệt
    name = re.sub(r"[^a-zA-Z0-9_\-]", "", name)
    return name[:120]


def _clean_html_to_text(html: str) -> str:
    """Extract text từ HTML thô (không cần BeautifulSoup)."""
    # Bỏ script, style, nav, footer
    html = re.sub(r"<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Bỏ HTML tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Decode HTML entities
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&#39;", "'").replace("&quot;", '"')
    # Chuẩn hóa whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def crawl_url(url: str, title: str, category: str, language: str, priority: int, output_dir: Path) -> Optional[Path]:
    """
    Crawl một URL và lưu thành PDF hoặc TXT.
    Trả về path file đã lưu hoặc None nếu thất bại.
    """
    try:
        import urllib.request
        import ssl

        # Tạo request với headers giả browser
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; HealthcareRAG/2.0; +https://github.com/healthcare-rag)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()

        # Nếu là PDF → lưu trực tiếp
        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            filename = _url_to_filename(url, category) + ".pdf"
            out_path = output_dir / filename
            out_path.write_bytes(raw)
            logger.success(f"  ✅ PDF: {filename} ({len(raw)//1024}KB)")
            return out_path

        # HTML → extract text → lưu PDF (qua reportlab) hoặc TXT
        encoding = "utf-8"
        for enc in ["utf-8", "utf-8-sig", "latin-1"]:
            try:
                html = raw.decode(enc)
                encoding = enc
                break
            except Exception:
                continue

        text = _clean_html_to_text(html)

        # Bỏ qua nếu quá ngắn (trang lỗi, redirect, etc.)
        if len(text) < 200:
            logger.warning(f"  ⚠ Bỏ qua {url[:60]} — nội dung quá ngắn ({len(text)} ký tự)")
            return None

        # Tạo metadata header
        meta = {
            "url": url,
            "title": title,
            "category": category,
            "language": language,
            "source_priority": priority,
            "source_type": "web_article",
            "crawled_at": datetime.now().isoformat(),
            "source_name": urlparse(url).netloc.replace("www.", ""),
            "document_title": title,
            "verified_by_doctor": False,
        }
        content = f"===METADATA===\n{json.dumps(meta, ensure_ascii=False, indent=2)}\n===CONTENT===\n{title}\n\n{text}"

        # Thử tạo PDF, fallback về TXT
        filename_base = _url_to_filename(url, category)
        pdf_saved = _save_as_pdf(content, title, output_dir / (filename_base + ".pdf"))
        if pdf_saved:
            logger.success(f"  ✅ PDF: {filename_base}.pdf ({len(text)//1024+1}KB text)")
            return output_dir / (filename_base + ".pdf")
        else:
            txt_path = output_dir / (filename_base + ".txt")
            txt_path.write_text(content, encoding="utf-8")
            logger.success(f"  ✅ TXT: {filename_base}.txt ({len(text)//1024+1}KB)")
            return txt_path

    except Exception as e:
        logger.error(f"  ✗ Lỗi crawl {url[:60]}: {e}")
        return None


def _save_as_pdf(content: str, title: str, out_path: Path) -> bool:
    """Lưu text thành PDF dùng reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Title"],
            fontSize=16,
            spaceAfter=12,
        )
        story.append(Paragraph(title[:200], title_style))
        story.append(Spacer(1, 12))

        # Body — chia đoạn để avoid PDF crash
        body_style = ParagraphStyle(
            "CustomBody",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            spaceAfter=6,
        )

        # Chỉ lấy phần CONTENT (bỏ metadata)
        if "===CONTENT===" in content:
            body_text = content.split("===CONTENT===", 1)[1].strip()
        else:
            body_text = content

        for para in body_text.split("\n\n"):
            para = para.strip()
            if not para:
                continue
            # Escape XML chars
            para = para.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            try:
                story.append(Paragraph(para[:2000], body_style))
                story.append(Spacer(1, 4))
            except Exception:
                continue

        doc.build(story)
        return True
    except ImportError:
        return False
    except Exception as e:
        logger.debug(f"reportlab error: {e}")
        if out_path.exists():
            out_path.unlink()
        return False


def crawl_category(
    category: str,
    sources: List[Dict],
    max_per_category: int = 10,
    skip_existing: bool = True,
    dry_run: bool = False,
) -> List[Path]:
    """Crawl tất cả URL của một danh mục."""
    # Xác định thư mục output
    cat_dir = PDF_BASE_DIR / category
    cat_dir.mkdir(parents=True, exist_ok=True)

    state = _load_state()
    saved_files = []

    logger.info(f"\n📂 Danh mục: {category}")
    logger.info(f"   {len(sources)} nguồn | Output: {cat_dir}")

    count = 0
    for source in sources:
        if count >= max_per_category:
            logger.info(f"   Đã đạt giới hạn {max_per_category} tài liệu")
            break

        url = source["url"]
        title = source["title"]
        language = source.get("language", "vi")
        priority = source.get("priority", 3)

        # Kiểm tra đã crawl chưa
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        if skip_existing and url_hash in state:
            logger.info(f"  ⏭ Bỏ qua (đã crawl): {title[:50]}")
            continue

        if dry_run:
            logger.info(f"  🔍 [DRY RUN] Sẽ crawl: {url}")
            continue

        logger.info(f"  🌐 Crawl: {title[:60]}")
        time.sleep(1.5)  # Rate limiting

        saved = crawl_url(url, title, category, language, priority, cat_dir)
        if saved:
            saved_files.append(saved)
            state[url_hash] = {
                "url": url,
                "title": title,
                "category": category,
                "saved_at": datetime.now().isoformat(),
                "file": str(saved.name),
            }
            _save_state(state)
            count += 1

    logger.info(f"   ✅ Crawl xong: {count} tài liệu mới")
    return saved_files


def run_crawler(
    categories: Optional[List[str]] = None,
    max_per_category: int = 10,
    skip_existing: bool = True,
    dry_run: bool = False,
    ingest_after: bool = False,
):
    """Chạy crawler cho các danh mục được chỉ định."""
    logger.info("=" * 60)
    logger.info("🕷  HEALTHCARE RAG — CRAWLER")
    logger.info("=" * 60)

    # Kiểm tra thư viện
    try:
        from reportlab.lib.pagesizes import A4
        logger.info("📦 reportlab: OK (PDF output)")
    except ImportError:
        logger.warning("⚠ reportlab chưa cài → sẽ lưu TXT thay PDF")
        logger.warning("  Cài: pip install reportlab")

    # Chọn danh mục
    if categories:
        sources_to_crawl = {k: v for k, v in CRAWL_SOURCES.items() if k in categories}
    else:
        sources_to_crawl = CRAWL_SOURCES

    logger.info(f"\n📋 Sẽ crawl {len(sources_to_crawl)} danh mục:")
    for cat in sources_to_crawl:
        logger.info(f"   - {cat} ({len(sources_to_crawl[cat])} nguồn)")

    if dry_run:
        logger.info("\n🔍 CHẾ ĐỘ DRY RUN — Chỉ xem, không tải")

    # Crawl từng danh mục
    all_saved = []
    for category, sources in sources_to_crawl.items():
        saved = crawl_category(
            category=category,
            sources=sources,
            max_per_category=max_per_category,
            skip_existing=skip_existing,
            dry_run=dry_run,
        )
        all_saved.extend(saved)

    logger.info("\n" + "=" * 60)
    logger.info(f"✅ CRAWLER XONG!")
    logger.info(f"   Tổng file mới: {len(all_saved)}")

    if all_saved:
        logger.info("\n   Files đã lưu:")
        for f in all_saved[:10]:
            logger.info(f"     - {f.relative_to(ROOT)}")
        if len(all_saved) > 10:
            logger.info(f"     ... và {len(all_saved)-10} file khác")

    # Tự động ingest
    if ingest_after and all_saved and not dry_run:
        logger.info("\n⚙ Bắt đầu ingest vào Qdrant...")
        try:
            from scripts.ingest import ingest_all
            ingest_all(PDF_BASE_DIR, incremental=True)
        except Exception as e:
            logger.error(f"Lỗi ingest: {e}")
            logger.info("Chạy thủ công: python scripts/ingest.py --incremental")

    return all_saved


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Crawler tài liệu y tế vào data/pdfs/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python scripts/crawler.py                        # Crawl tất cả
  python scripts/crawler.py --category diet        # Chỉ crawl diet
  python scripts/crawler.py --category cardiovascular neuropathy
  python scripts/crawler.py --dry-run              # Xem URL không tải
  python scripts/crawler.py --ingest               # Crawl + ingest luôn
  python scripts/crawler.py --max-per-category 3  # Giới hạn 3 file/danh mục
  python scripts/crawler.py --force               # Crawl lại kể cả đã có
        """
    )
    parser.add_argument(
        "--category", "-c",
        nargs="+",
        choices=list(CRAWL_SOURCES.keys()),
        help="Danh mục cần crawl (mặc định: tất cả)",
    )
    parser.add_argument(
        "--max-per-category", "-m",
        type=int, default=10,
        help="Số tài liệu tối đa mỗi danh mục (mặc định: 10)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ xem URL sẽ crawl, không tải",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Tự động ingest vào Qdrant sau khi crawl",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Crawl lại kể cả URL đã từng crawl",
    )
    args = parser.parse_args()

    run_crawler(
        categories=args.category,
        max_per_category=args.max_per_category,
        skip_existing=not args.force,
        dry_run=args.dry_run,
        ingest_after=args.ingest,
    )
