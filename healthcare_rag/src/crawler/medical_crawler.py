"""
================================================================
BƯỚC 1: CRAWLER — Thu Thập Tài Liệu Y Khoa Về Tiểu Đường
================================================================

CHANGELOG (v2 — Deep Crawl Fix):
─────────────────────────────────────────────────────────────
  VẤN ĐỀ CŨ:
    HealthcareCrawler chỉ fetch đúng 1 URL rồi dừng.
    Trang kcb.vn (và tương tự) có cấu trúc:
      Landing page (body ngắn)
        ├── Link PDF → "Hướng dẫn chẩn đoán.pdf"   ← BỎ SÓT
        └── Link sub-page → "/chi-tiet-quy-trinh"   ← BỎ SÓT

  FIX CHÍNH (HealthcareCrawler):
    1. MedicalSource có thêm `deep_crawl: bool` và `max_depth: int`
       - deep_crawl=True  → follow PDF + sub-page links
       - max_depth        → giới hạn độ sâu (tránh crawl toàn site)

    2. `_extract_links(html, base_url)` — phân loại links:
       - PDF links  (.pdf, /download/, /tai-lieu/) → download file
       - Sub-page links (cùng domain, path khác) → crawl tiếp
       - External links → bỏ qua

    3. `crawl_source_deep(source)` — BFS với visited set:
       Queue: [(url, depth)]
       Mỗi page: fetch → save text + collect next links
       PDF links: download riêng vào data/pdfs/

    4. `_is_same_domain(url, base)` — chỉ follow link trong
       cùng domain (không leak sang external sites)

    5. `_is_content_page(url)` — lọc bỏ link không cần thiết:
       login, logout, register, feed, sitemap, robots.txt...

  FIX PHỤ (ADA Crawler):
    Không đổi logic — vẫn hoạt động tốt.

CÁCH CHẠY:
    python medical_crawler.py
    python medical_crawler.py --ada-only
    python medical_crawler.py --general-only
    python medical_crawler.py --demo
    python medical_crawler.py --sections s002 s006 s009
================================================================
"""

import os
import re
import sys
import time
import json
import hashlib
import argparse
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse
from collections import deque
from datetime import datetime


# ── Cấu hình thư mục ────────────────────────────────────────
RAW_DIR = Path("data/raw")
PDF_DIR = Path("data/pdfs")
RAW_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging đơn giản ────────────────────────────────────────
class Log:
    @staticmethod
    def info(msg):    print(f"  ℹ  {msg}")
    @staticmethod
    def success(msg): print(f"  ✅ {msg}")
    @staticmethod
    def warning(msg): print(f"  ⚠  {msg}")
    @staticmethod
    def error(msg):   print(f"  ✗  {msg}")
    @staticmethod
    def section(msg): print(f"\n{'─'*55}\n  {msg}\n{'─'*55}")
    @staticmethod
    def deep(msg):    print(f"      ↳ {msg}")   # indented cho deep crawl

logger = Log()

# ── Headers giả lập trình duyệt ─────────────────────────────
HEADERS_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.google.com/",
    "DNT": "1",
}

HEADERS_PDF = {
    **HEADERS_BROWSER,
    "Accept": "application/pdf,application/octet-stream,*/*",
}

# ── URL patterns cần BỎ QUA khi deep crawl ─────────────────
SKIP_URL_PATTERNS = [
    r"/login", r"/logout", r"/register", r"/signup", r"/dang-ky",
    r"/dang-nhap", r"/thoat", r"#", r"javascript:", r"mailto:",
    r"tel:", r"/feed", r"/rss", r"/sitemap", r"robots\.txt",
    r"/search\?", r"/tag/", r"/author/", r"/page/\d+",  # pagination handled separately
    r"\?share=", r"\?replytocom=", r"\.jpg$", r"\.png$",
    r"\.gif$", r"\.css$", r"\.js$", r"\.xml$",
]

# ── Patterns nhận diện PDF link ──────────────────────────────
PDF_URL_PATTERNS = [
    r"\.pdf($|\?)",
    r"/download/",
    r"/tai-lieu/",
    r"/tai-xuong/",
    r"type=pdf",
    r"format=pdf",
]


# ================================================================
# DATA CLASSES
# ================================================================

@dataclass
class MedicalSource:
    """Mô tả một nguồn tài liệu y khoa cần crawl."""
    name: str
    url: str
    category: str
    selector: str = "article"
    language: str = "vi"
    title: str = ""
    source_type: str = "health_website"
    source_priority: int = 4
    verified_by_doctor: bool = False
    published_date: str = ""
    condition_tags: List[str] = field(default_factory=list)

    # ── THÊM MỚI: Deep crawl settings ───────────────────────
    deep_crawl: bool = False
    """
    True  → sau khi fetch trang gốc, tự động follow:
              • PDF links trong page → download PDF
              • Sub-page links (cùng domain) → crawl tiếp
    False → hành vi cũ: chỉ fetch đúng URL này
    """

    max_depth: int = 2
    """
    Độ sâu tối đa khi deep_crawl=True:
      depth=0 → chỉ URL gốc
      depth=1 → URL gốc + links trực tiếp
      depth=2 → thêm 1 cấp nữa (default)
    Tăng lên nếu trang có cấu trúc sâu hơn.
    """

    max_pages: int = 50
    """
    Số trang tối đa để crawl (tránh crawl toàn bộ site).
    """

    follow_pdf: bool = True
    """
    True → download cả file PDF tìm thấy trong trang.
    """

    allowed_path_prefix: str = ""
    """
    Nếu đặt (ví dụ "/tin-tuc/"), chỉ follow links có path
    bắt đầu bằng prefix này. Giúp giới hạn phạm vi crawl.
    Ví dụ: allowed_path_prefix="/benh/" chỉ crawl trong /benh/
    """


@dataclass
class ADASection:
    """Mô tả một section của ADA Standards of Care."""
    section_id: str
    title: str
    doi: str
    category: str
    condition_tags: List[str] = field(default_factory=list)


# ================================================================
# ADA STANDARDS OF CARE — 2026 SECTIONS
# ================================================================

ADA_2026_SECTIONS: List[ADASection] = [
    ADASection("sint", "Introduction and Methodology",
               "https://doi.org/10.2337/dc26-sint", "general", ["methodology"]),
    ADASection("srev", "Summary of Revisions 2026",
               "https://doi.org/10.2337/dc26-srev", "general", ["revisions"]),
    ADASection("sdis", "Disclosures",
               "https://doi.org/10.2337/dc26-sdis", "general", []),
    ADASection("in01", "Index",
               "https://doi.org/10.2337/dc26-in01", "general", []),
    ADASection("s001", "Improving Care and Promoting Health in Populations",
               "https://doi.org/10.2337/dc26-s001", "general",
               ["population_health", "diabetes"]),
    ADASection("s002", "Diagnosis and Classification of Diabetes",
               "https://doi.org/10.2337/dc26-s002", "diagnosis",
               ["diagnosis", "classification", "type1_diabetes", "type2_diabetes"]),
    ADASection("s003", "Prevention or Delay of Diabetes and Associated Comorbidities",
               "https://doi.org/10.2337/dc26-s003", "general",
               ["prevention", "prediabetes", "comorbidities"]),
    ADASection("s004", "Comprehensive Medical Evaluation and Assessment of Comorbidities",
               "https://doi.org/10.2337/dc26-s004", "diagnosis",
               ["comorbidities", "evaluation", "screening"]),
    ADASection("s005", "Facilitating Positive Health Behaviors and Well-being",
               "https://doi.org/10.2337/dc26-s005", "lifestyle",
               ["diet", "exercise", "mental_health", "behavior"]),
    ADASection("s006", "Glycemic Goals and Hypoglycemia",
               "https://doi.org/10.2337/dc26-s006", "blood_glucose",
               ["hba1c", "blood_glucose", "hypoglycemia", "targets"]),
    ADASection("s007", "Diabetes Technology",
               "https://doi.org/10.2337/dc26-s007", "blood_glucose",
               ["cgm", "insulin_pump", "technology", "monitoring"]),
    ADASection("s008", "Obesity and Weight Management",
               "https://doi.org/10.2337/dc26-s008", "lifestyle",
               ["obesity", "weight_management", "type2_diabetes", "prevention"]),
    ADASection("s009", "Pharmacologic Approaches to Glycemic Treatment",
               "https://doi.org/10.2337/dc26-s009", "medication",
               ["metformin", "insulin", "glp1", "sglt2", "medication",
                "type2_diabetes", "treatment"]),
    ADASection("s010", "Cardiovascular Disease and Risk Management",
               "https://doi.org/10.2337/dc26-s010", "complication",
               ["cardiovascular", "hypertension", "dyslipidemia", "risk"]),
    ADASection("s011", "Chronic Kidney Disease and Risk Management",
               "https://doi.org/10.2337/dc26-s011", "complication",
               ["nephropathy", "ckd", "kidney", "egfr"]),
    ADASection("s012", "Retinopathy, Neuropathy, and Foot Care",
               "https://doi.org/10.2337/dc26-s012", "complication",
               ["retinopathy", "neuropathy", "foot_care", "complication"]),
    ADASection("s013", "Older Adults",
               "https://doi.org/10.2337/dc26-S013", "general",
               ["elderly", "older_adults", "geriatric"]),
    ADASection("s014", "Children and Adolescents",
               "https://doi.org/10.2337/dc26-s014", "general",
               ["children", "adolescents", "pediatric", "type1_diabetes"]),
    ADASection("s015", "Management of Diabetes in Pregnancy",
               "https://doi.org/10.2337/dc26-s015", "general",
               ["pregnancy", "gestational_diabetes", "gdm"]),
    ADASection("s016", "Diabetes Care in the Hospital",
               "https://doi.org/10.2337/dc26-s016", "general",
               ["hospital", "inpatient", "critical_care"]),
    ADASection("s017", "Diabetes Advocacy",
               "https://doi.org/10.2337/dc26-s017", "general",
               ["advocacy", "policy", "social_determinants"]),
]


# ================================================================
# DANH SÁCH NGUỒN — v2: bật deep_crawl cho các trang phức tạp
# ================================================================

MEDICAL_SOURCES: List[MedicalSource] = [

    # ── HƯỚNG DẪN CHÍNH THỨC VIỆT NAM ──────────────────────
    # BẬT deep_crawl=True — trang này chỉ có intro ngắn + links
    # Cần follow để lấy PDF hướng dẫn thực sự
    MedicalSource(
        name="kcb_quy_trinh_lam_sang_dai_thao_duong",
        title="Quy trình lâm sàng điều trị đái tháo đường",
        url="https://daithaoduong.kcb.vn/quy-trinh-lam-sang-dieu-tri-dai-thao-duong",
        category="diagnosis",
        selector="main",
        language="vi",
        source_type="official_guideline",
        source_priority=1,
        verified_by_doctor=True,
        published_date="2017-08-21",
        condition_tags=["type2_diabetes"],
        deep_crawl=True,        # ← BẬT: follow PDF + sub-page links
        max_depth=2,
        max_pages=30,
        follow_pdf=True,
        # Chỉ follow links trong domain daithaoduong.kcb.vn
    ),

    # BẬT deep_crawl để crawl thêm các tài liệu liên quan
    MedicalSource(
        name="vncdc_quan_ly_benh_dai_thao_duong",
        title="Quản lý bệnh đái tháo đường - VNCDC",
        url="https://vncdc.gov.vn/quan-ly-benh-dai-thao-duong-nd14581.html",
        category="diagnosis",
        selector="main",
        language="vi",
        source_type="government_health",
        source_priority=2,
        verified_by_doctor=True,
        condition_tags=["type2_diabetes"],
        deep_crawl=True,
        max_depth=1,            # vncdc: depth=1 là đủ (tránh crawl quá nhiều)
        max_pages=20,
        follow_pdf=True,
        allowed_path_prefix="/",  # Chấp nhận mọi path trong vncdc.gov.vn
    ),

    MedicalSource(
        name="vncdc_dinh_duong_dai_thao_duong",
        title="Dinh dưỡng hợp lý cho người bệnh đái tháo đường - VNCDC",
        url="https://vncdc.gov.vn/dinh-duong-hop-ly-doi-voi-nguoi-bi-benh-dai-thao-duong-nd14913.html",
        category="diet",
        selector="main",
        language="vi",
        source_type="government_health",
        source_priority=2,
        verified_by_doctor=True,
        condition_tags=["type2_diabetes", "nutrition"],
        deep_crawl=True,
        max_depth=1,
        max_pages=15,
        follow_pdf=True,
    ),

    # ── CDC / NIH — trang lớn, không cần deep_crawl quá sâu ─
    MedicalSource(
        name="cdc_diabetes_basics",
        title="CDC Diabetes Basics",
        url="https://www.cdc.gov/diabetes/about/index.html",
        category="general",
        selector="main",
        language="en",
        source_type="government_health",
        source_priority=2,
        verified_by_doctor=True,
        condition_tags=["diabetes"],
        deep_crawl=True,
        max_depth=1,
        max_pages=15,
        follow_pdf=True,
        allowed_path_prefix="/diabetes/",  # Chỉ lấy trang trong /diabetes/
    ),

    MedicalSource(
        name="cdc_manage_blood_sugar",
        title="CDC Manage Blood Sugar",
        url="https://www.cdc.gov/diabetes/treatment/index.html",
        category="blood_glucose",
        selector="main",
        language="en",
        source_type="government_health",
        source_priority=2,
        verified_by_doctor=True,
        condition_tags=["blood_glucose"],
        deep_crawl=True,
        max_depth=1,
        max_pages=10,
        follow_pdf=True,
        allowed_path_prefix="/diabetes/treatment/",
    ),

    MedicalSource(
        name="cdc_treatment_low_blood_sugar",
        title="CDC Treatment of Low Blood Sugar (Hypoglycemia)",
        url="https://www.cdc.gov/diabetes/treatment/treatment-low-blood-sugar-hypoglycemia.html",
        category="emergency",
        selector="main",
        language="en",
        source_type="government_health",
        source_priority=2,
        verified_by_doctor=True,
        condition_tags=["hypoglycemia", "blood_glucose"],
        deep_crawl=False,  # Trang này đủ chi tiết, không cần deep
    ),

    MedicalSource(
        name="niddk_healthy_living_diabetes",
        title="NIDDK Healthy Living with Diabetes",
        url="https://www.niddk.nih.gov/health-information/diabetes/overview/diet-eating-physical-activity",
        category="diet",
        selector="main",
        language="en",
        source_type="government_health",
        source_priority=2,
        verified_by_doctor=True,
        condition_tags=["diet", "exercise"],
        deep_crawl=True,
        max_depth=1,
        max_pages=10,
        follow_pdf=True,
        allowed_path_prefix="/health-information/diabetes/",
    ),

    MedicalSource(
        name="niddk_insulin_medicines",
        title="NIDDK Insulin, Medicines, and Other Diabetes Treatments",
        url="https://www.niddk.nih.gov/health-information/diabetes/overview/insulin-medicines-treatments",
        category="medication",
        selector="main",
        language="en",
        source_type="government_health",
        source_priority=2,
        verified_by_doctor=True,
        condition_tags=["medication", "insulin"],
        deep_crawl=True,
        max_depth=1,
        max_pages=10,
        follow_pdf=True,
        allowed_path_prefix="/health-information/diabetes/",
    ),

    MedicalSource(
        name="niddk_low_blood_glucose",
        title="NIDDK Low Blood Glucose (Hypoglycemia)",
        url="https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/low-blood-glucose-hypoglycemia",
        category="emergency",
        selector="main",
        language="en",
        source_type="government_health",
        source_priority=2,
        verified_by_doctor=True,
        condition_tags=["hypoglycemia", "blood_glucose"],
        deep_crawl=False,
    ),

    MedicalSource(
        name="who_diabetes_facts",
        title="WHO Diabetes Fact Sheet",
        url="https://www.who.int/news-room/fact-sheets/detail/diabetes",
        category="general",
        selector=".sf-detail-body-wrapper",
        language="en",
        source_type="government_health",
        source_priority=2,
        verified_by_doctor=True,
        condition_tags=["diabetes"],
        deep_crawl=False,  # WHO fact sheet tự đủ
    ),

    # ── NICE GUIDELINE ───────────────────────────────────────
    MedicalSource(
        name="nice_ng28_type2_diabetes",
        title="NICE NG28 Type 2 Diabetes in Adults: Management",
        url="https://www.nice.org.uk/guidance/ng28",
        category="medication",
        selector=".guidance-pane",
        language="en",
        source_type="official_guideline",
        source_priority=1,
        verified_by_doctor=True,
        condition_tags=["type2_diabetes", "medication"],
        deep_crawl=True,
        max_depth=2,
        max_pages=20,
        follow_pdf=True,
        allowed_path_prefix="/guidance/ng28",
    ),

    # ── VINMEC ───────────────────────────────────────────────
    MedicalSource(
        name="vinmec_tieu_duong_type2",
        title="Bệnh tiểu đường type 2 - Vinmec",
        url="https://www.vinmec.com/vi/benh/tieu-duong-typ-2-3404/",
        category="general",
        selector=".detail-content",
        language="vi",
        source_type="hospital_website",
        source_priority=3,
        condition_tags=["type2_diabetes"],
        deep_crawl=True,
        max_depth=1,
        max_pages=15,
        follow_pdf=True,
        allowed_path_prefix="/vi/",
    ),

    MedicalSource(
        name="vinmec_che_do_an_tieu_duong",
        title="Thực phẩm tốt cho người bệnh tiểu đường - Vinmec",
        url="https://www.vinmec.com/vi/tin-tuc/thong-tin-suc-khoe/thuc-pham-tot-cho-nguoi-benh-tieu-duong/",
        category="diet",
        selector=".detail-content",
        language="vi",
        source_type="hospital_website",
        source_priority=3,
        condition_tags=["type2_diabetes", "nutrition"],
        deep_crawl=True,
        max_depth=1,
        max_pages=15,
        follow_pdf=True,
        allowed_path_prefix="/vi/tin-tuc/",
    ),

    MedicalSource(
        name="vinmec_insulin",
        title="Insulin trong điều trị bệnh tiểu đường - Vinmec",
        url="https://www.vinmec.com/vi/tin-tuc/thong-tin-suc-khoe/insulin-trong-dieu-tri-benh-tieu-duong/",
        category="medication",
        selector=".detail-content",
        language="vi",
        source_type="hospital_website",
        source_priority=3,
        condition_tags=["insulin", "medication"],
        deep_crawl=False,
    ),
]


# ================================================================
# UTILITY FUNCTIONS
# ================================================================

def normalize_url(url: str) -> str:
    """
    Chuẩn hóa URL: bỏ fragment (#...), trailing slash, query string thừa.
    Mục đích: tránh crawl cùng trang nhiều lần do URL format khác nhau.
    """
    parsed = urlparse(url)
    # Bỏ fragment (#section)
    clean = parsed._replace(fragment="")
    # Normalize path (bỏ double slash)
    path = re.sub(r"/{2,}", "/", clean.path)
    clean = clean._replace(path=path)
    return urlunparse(clean)


def url_to_filename(url: str, prefix: str = "") -> str:
    """
    Tạo filename an toàn từ URL:
      https://example.com/a/b/c → example_com__a__b__c.txt
    Dùng hash nếu URL quá dài.
    """
    parsed = urlparse(url)
    slug = parsed.netloc + parsed.path
    slug = re.sub(r"[^\w\-]", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")

    if len(slug) > 120:
        # Dùng hash để tránh filename quá dài
        slug = slug[:80] + "_" + hashlib.md5(url.encode()).hexdigest()[:8]

    return f"{prefix}__{slug}" if prefix else slug


def is_pdf_url(url: str) -> bool:
    """Kiểm tra URL có phải link đến PDF không."""
    url_lower = url.lower()
    return any(re.search(p, url_lower) for p in PDF_URL_PATTERNS)


def is_skip_url(url: str) -> bool:
    """Kiểm tra URL có nên bỏ qua không (login, feed, asset...)."""
    url_lower = url.lower()
    return any(re.search(p, url_lower) for p in SKIP_URL_PATTERNS)


def is_same_domain(url: str, base_url: str) -> bool:
    """
    Kiểm tra URL có cùng domain với base_url không.
    Ví dụ: base=daithaoduong.kcb.vn → chỉ follow links trong domain này.
    """
    try:
        base_host = urlparse(base_url).netloc.lower()
        url_host = urlparse(url).netloc.lower()
        # Cho phép cả subdomain: www.example.com == example.com
        return url_host == base_host or url_host.endswith("." + base_host) \
               or base_host.endswith("." + url_host)
    except Exception:
        return False


def is_allowed_path(url: str, prefix: str) -> bool:
    """
    Nếu có allowed_path_prefix, chỉ follow URL có path bắt đầu bằng prefix.
    prefix="" → không giới hạn (follow tất cả cùng domain).
    """
    if not prefix:
        return True
    path = urlparse(url).path
    return path.startswith(prefix)


# ================================================================
# CLASS 1: ADA STANDARDS OF CARE CRAWLER (giữ nguyên v1)
# ================================================================

class ADAStandardsCrawler:
    """
    Crawler chuyên biệt cho ADA Standards of Care.
    Logic không đổi — v1 đã hoạt động tốt.
    """

    PDF_LINK_SELECTORS = [
        "a.article-pdfLink",
        "a[data-article-link-type='pdf']",
        "a.al-link.pdf-link",
        "a[href*='article-pdf']",
        "a[href*='.pdf']",
    ]

    ARTICLE_SELECTORS = [
        ".widget-ArticleFulltext",
        ".article-section__body",
        ".article-body",
        "#article-content",
        "section.article",
        "[data-widget-def='ArticleFulltext']",
        "main article",
        "main",
    ]

    def __init__(self, pdf_dir: Path = PDF_DIR, raw_dir: Path = RAW_DIR,
                 delay: float = 3.0, demo_mode: bool = False):
        self.pdf_dir = pdf_dir
        self.raw_dir = raw_dir
        self.delay = delay
        self.demo_mode = demo_mode
        self.session = requests.Session()
        self.session.headers.update(HEADERS_BROWSER)
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _follow_doi(self, doi_url: str) -> Optional[str]:
        logger.info(f"Follow DOI: {doi_url}")
        try:
            resp = self.session.get(doi_url, allow_redirects=True, timeout=20, verify=False)
            final_url = resp.url
            if "doi.org" in final_url:
                logger.warning(f"  DOI chưa resolve: {final_url}")
                return None
            logger.info(f"  → Resolved: {final_url}")
            return final_url
        except Exception as e:
            logger.error(f"  Lỗi follow DOI: {e}")
            return None

    def _find_pdf_link(self, html: str, base_url: str) -> Optional[str]:
        soup = BeautifulSoup(html, "lxml")
        for selector in ["a.article-pdfLink", "a[data-article-link-type='pdf']",
                         "a.al-link.pdf-link"]:
            el = soup.select_one(selector)
            if el and el.get("href"):
                href = el["href"]
                return urljoin(base_url, href) if href.startswith("/") else href
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "article-pdf" in href.lower() or (
                href.endswith(".pdf") and "dc26" in href.lower()
            ):
                return urljoin(base_url, href) if href.startswith("/") else href
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).lower()
            if text in ["pdf", "full text pdf", "download pdf", "view pdf"]:
                href = a["href"]
                if "pdf" in href.lower():
                    return urljoin(base_url, href) if href.startswith("/") else href
        return None

    def _extract_article_text(self, html: str, section: ADASection) -> str:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "aside", "iframe", ".sidebar"]):
            tag.decompose()
        content = None
        for sel in self.ARTICLE_SELECTORS:
            content = soup.select_one(sel)
            if content:
                break
        if not content:
            content = soup.find("body")
        text = content.get_text(separator="\n") if content else ""
        lines = [l.strip() for l in text.splitlines() if l.strip() and len(l.strip()) > 2]
        return "\n".join(lines)

    def _download_pdf(self, pdf_url: str, save_path: Path) -> bool:
        logger.info(f"  Download PDF: {pdf_url}")
        try:
            resp = self.session.get(
                pdf_url,
                headers={**HEADERS_PDF, "Referer": "https://diabetesjournals.org/"},
                stream=True, timeout=60, verify=False,
            )
            resp.raise_for_status()
            content = b"".join(resp.iter_content(chunk_size=8192))
            ctype = resp.headers.get("Content-Type", "")
            if "pdf" not in ctype.lower() and "octet-stream" not in ctype.lower():
                if len(content) < 10_000:
                    return False
            save_path.write_bytes(content)
            logger.success(f"  PDF: {save_path.name} ({save_path.stat().st_size // 1024} KB)")
            return True
        except Exception as e:
            logger.error(f"  Lỗi PDF: {e}")
            return False

    def _save_metadata_txt(self, section: ADASection, text: str,
                            article_url: str, pdf_path: Optional[Path] = None):
        filename = f"ada2026__{section.section_id}.txt"
        filepath = self.raw_dir / filename
        metadata = {
            "source_name": f"ada2026_{section.section_id}",
            "document_title": f"ADA 2026 Standards of Care — {section.title}",
            "url": article_url,
            "doi": section.doi,
            "category": section.category,
            "language": "en",
            "source_type": "official_guideline",
            "source_priority": 1,
            "verified_by_doctor": True,
            "published_date": "2025-12-01",
            "condition_tags": section.condition_tags,
            "crawled_at": datetime.now().isoformat(),
            "pdf_saved": str(pdf_path) if pdf_path else None,
            "char_count": len(text),
        }
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("===METADATA===\n")
            f.write(json.dumps(metadata, ensure_ascii=False, indent=2))
            f.write("\n===CONTENT===\n")
            f.write(text)
        return filepath

    def crawl_section(self, section: ADASection, force: bool = False) -> dict:
        print(f"\n  [{section.section_id.upper()}] {section.title}")
        pdf_path = self.pdf_dir / f"ada2026_{section.section_id}.pdf"
        txt_path = self.raw_dir / f"ada2026__{section.section_id}.txt"
        if pdf_path.exists() and not force:
            logger.info(f"  ⏭ Đã có PDF: {pdf_path.name}")
            return {"status": "skipped", "section": section.section_id, "type": "pdf"}
        if txt_path.exists() and not force:
            logger.info(f"  ⏭ Đã có TXT: {txt_path.name}")
            return {"status": "skipped", "section": section.section_id, "type": "txt"}
        if force:
            if pdf_path.exists():
                pdf_path.unlink()
            if txt_path.exists():
                txt_path.unlink()
        if self.demo_mode:
            logger.info("  [DEMO] Bỏ qua")
            return {"status": "demo", "section": section.section_id}

        article_url = self._follow_doi(section.doi)
        if not article_url:
            return {"status": "failed", "section": section.section_id,
                    "reason": "doi_not_resolved"}
        time.sleep(1)

        try:
            resp = self.session.get(article_url, timeout=20, verify=False)
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            logger.error(f"  Fetch thất bại: {e}")
            return {"status": "failed", "section": section.section_id, "reason": str(e)}

        pdf_url = self._find_pdf_link(html, article_url)
        if pdf_url:
            ok = self._download_pdf(pdf_url, pdf_path)
            if ok:
                text = self._extract_article_text(html, section)
                self._save_metadata_txt(section, text, article_url, pdf_path)
                return {"status": "success", "section": section.section_id,
                        "type": "pdf", "pdf_path": str(pdf_path),
                        "pdf_size_kb": pdf_path.stat().st_size // 1024}

        logger.warning("  PDF không tải được, fallback sang text")
        text = self._extract_article_text(html, section)
        if len(text) < 300:
            logger.error(f"  Text quá ngắn ({len(text)} ký tự)")
            return {"status": "failed", "section": section.section_id,
                    "reason": "content_too_short"}
        saved = self._save_metadata_txt(section, text, article_url)
        logger.success(f"  Text: {saved.name} ({len(text):,} ký tự)")
        return {"status": "success", "section": section.section_id,
                "type": "text", "txt_path": str(saved), "chars": len(text)}

    def crawl_all_sections(self, sections: List[ADASection] = None, force: bool = False) -> List[dict]:
        sections = sections or ADA_2026_SECTIONS
        logger.section(f"ADA STANDARDS OF CARE 2026 — {len(sections)} sections")
        results = []
        for i, section in enumerate(sections, 1):
            print(f"\n  [{i:02d}/{len(sections)}]", end="")
            result = self.crawl_section(section, force=force)
            results.append(result)
            if i < len(sections) and result.get("status") != "skipped":
                print(f"  ⏳ Chờ {self.delay}s...")
                time.sleep(self.delay)

        pdfs    = [r for r in results if r.get("type") == "pdf" and r.get("status") == "success"]
        texts   = [r for r in results if r.get("type") == "text" and r.get("status") == "success"]
        skipped = [r for r in results if r.get("status") == "skipped"]
        failed  = [r for r in results if r.get("status") == "failed"]

        logger.section("KẾT QUẢ ADA")
        print(f"  ✅ PDF: {len(pdfs)} | 📄 Text: {len(texts)} | ⏭ Skip: {len(skipped)} | ✗ Fail: {len(failed)}")

        report = self.pdf_dir / "ada2026_crawl_report.json"
        with open(report, "w", encoding="utf-8") as f:
            json.dump({"crawled_at": datetime.now().isoformat(),
                       "total": len(sections), "results": results},
                      f, ensure_ascii=False, indent=2)
        return results


# ================================================================
# CLASS 2: GENERAL HTML CRAWLER v2 — với Deep Crawl
# ================================================================

class HealthcareCrawler:
    """
    Crawler HTML đa năng v2.

    THÊM MỚI so với v1:
    ─────────────────────────────────────────────────────────
    deep_crawl mode (khi source.deep_crawl = True):

    BFS Queue: [(url, depth)]
    ┌─────────────────────────────────────────────────────┐
    │  Fetch page → extract text → save                   │
    │       │                                             │
    │       ├── Tìm tất cả links trong page              │
    │       │                                             │
    │       ├── PDF links → download_pdf()                │
    │       │    (cùng hoặc khác domain đều ok)           │
    │       │                                             │
    │       └── Sub-page links (cùng domain + depth<max) │
    │            → thêm vào queue                        │
    └─────────────────────────────────────────────────────┘

    Điều kiện để follow sub-page link:
      ✓ Cùng domain với source.url
      ✓ Nếu có allowed_path_prefix → path phải match
      ✓ Chưa trong visited set
      ✓ Không match SKIP_URL_PATTERNS
      ✓ depth < source.max_depth
      ✓ Tổng pages < source.max_pages
    """

    FALLBACK_SELECTORS = [
        "main", "article", "[role='main']",
        ".post-content", ".entry-content",
        ".article-body", ".page-content",
        ".detail-content", ".content-detail",
        ".single-post__content", "#content", ".content",
    ]

    def __init__(self, output_dir: Path = RAW_DIR, pdf_dir: Path = PDF_DIR,
                 delay: float = 2.5):
        self.output_dir = output_dir
        self.pdf_dir = pdf_dir
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(HEADERS_BROWSER)
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ── Fetch helpers ────────────────────────────────────────

    def _fetch_html(self, url: str, retries: int = 3) -> Optional[str]:
        """Tải HTML với retry."""
        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=20, verify=False)
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding
                return resp.text
            except requests.RequestException as e:
                wait = self.delay * (attempt + 1)
                logger.warning(f"  Thử {attempt+1}/{retries}: {e}")
                if attempt < retries - 1:
                    time.sleep(wait)
        logger.error(f"  Không tải được: {url}")
        return None

    def _download_pdf(self, pdf_url: str, source: MedicalSource, force: bool = False) -> Optional[Path]:
        """
        Download PDF từ pdf_url, lưu vào data/pdfs/.
        Trả về path nếu thành công, None nếu thất bại.
        """
        filename = url_to_filename(pdf_url, prefix=source.name) + ".pdf"
        save_path = self.pdf_dir / filename

        if save_path.exists() and not force:
            logger.deep(f"⏭ PDF đã có: {filename}")
            return save_path
        if force and save_path.exists():
            save_path.unlink()

        logger.deep(f"📥 Download PDF: {pdf_url[:80]}...")
        try:
            resp = self.session.get(
                pdf_url,
                headers={**HEADERS_PDF, "Referer": source.url},
                stream=True, timeout=60, verify=False,
            )
            resp.raise_for_status()
            content = b"".join(resp.iter_content(chunk_size=8192))

            # Xác minh có phải PDF thật không
            if len(content) < 5_000:
                logger.warning(f"  File quá nhỏ ({len(content)} bytes), bỏ qua")
                return None

            ctype = resp.headers.get("Content-Type", "")
            is_pdf = ("pdf" in ctype.lower() or "octet-stream" in ctype.lower()
                      or content[:4] == b"%PDF")
            if not is_pdf:
                logger.warning(f"  Không phải PDF (Content-Type: {ctype[:50]})")
                return None

            save_path.write_bytes(content)
            size_kb = save_path.stat().st_size // 1024
            logger.success(f"  PDF lưu: {filename} ({size_kb} KB)")
            return save_path

        except Exception as e:
            logger.error(f"  Lỗi download PDF: {e}")
            return None

    def _collect_url_candidates(self, soup: BeautifulSoup) -> List[str]:
        """
        Thu thập các URL có thể là link thật từ nhiều kiểu HTML khác nhau:
        - <a href="...">
        - <iframe src="...">, <embed src="...">, <object data="...">
        - data-href / data-url / data-src
        - onclick chứa URL
        """
        candidates: List[str] = []
        selectors = [
            "a[href]", "area[href]", "iframe[src]", "embed[src]",
            "object[data]", "source[src]", "[data-href]", "[data-url]",
            "[data-src]", "[onclick]",
        ]
        url_pattern = re.compile(r"(https?://[^'\"\\s>)+]+|/[^'\"\\s>)+]+)")

        for element in soup.select(", ".join(selectors)):
            for attr in ("href", "src", "data", "data-href", "data-url", "data-src"):
                value = element.get(attr)
                if value:
                    candidates.append(value.strip())

            onclick = element.get("onclick", "")
            if onclick:
                for match in url_pattern.findall(onclick):
                    candidates.append(match.strip())

        return candidates

    # ── Link extraction ──────────────────────────────────────

    def _extract_links(
        self, html: str, page_url: str, source: MedicalSource
    ) -> Tuple[List[str], List[str]]:
        """
        Phân tích HTML và chia links thành 2 loại:
          pdf_links  → list URL của PDF cần download
          page_links → list URL của sub-page cần crawl tiếp

        Logic:
          1. Collect tất cả <a href> trong page
          2. Resolve relative URLs (urljoin)
          3. Phân loại:
             - is_pdf_url(href)           → pdf_links
             - is_same_domain + allowed_path
               + not skip + not pdf       → page_links
        """
        soup = BeautifulSoup(html, "lxml")
        pdf_links: List[str] = []
        page_links: List[str] = []

        for raw_url in self._collect_url_candidates(soup):
            if not raw_url:
                continue

            full_url = normalize_url(urljoin(page_url, raw_url))
            if not full_url.startswith(("http://", "https://")):
                continue

            if is_pdf_url(full_url):
                if source.follow_pdf:
                    pdf_links.append(full_url)
                continue

            if (is_same_domain(full_url, source.url)
                    and is_allowed_path(full_url, source.allowed_path_prefix)
                    and not is_skip_url(full_url)):
                page_links.append(full_url)

        # Deduplicate
        return list(dict.fromkeys(pdf_links)), list(dict.fromkeys(page_links))

    # ── Text extraction ──────────────────────────────────────

    def _extract_text(self, html: str, source: MedicalSource) -> Optional[str]:
        """Parse HTML → clean text."""
        soup = BeautifulSoup(html, "lxml")
        for sel in ["script", "style", "nav", "footer", "header",
                    "aside", "iframe", "noscript", ".advertisement",
                    ".ads", ".sidebar", "[class*='banner']", "[class*='popup']",
                    ".cookie-notice", ".cookie-banner", ".breadcrumb"]:
            for tag in soup.select(sel):
                tag.decompose()

        content = soup.select_one(source.selector)
        if not content:
            for fallback in self.FALLBACK_SELECTORS:
                content = soup.select_one(fallback)
                if content:
                    break

        raw = content.get_text(separator="\n") if content else soup.get_text(separator="\n")
        lines = [l.strip() for l in raw.splitlines() if l.strip() and len(l.strip()) > 3]
        return "\n".join(lines)

    # ── Save helpers ─────────────────────────────────────────

    def _save_text(self, source: MedicalSource, text: str,
                   url: str = "", page_index: int = 0) -> Path:
        """
        Lưu text + metadata vào file.
        page_index=0 → trang gốc (dùng tên cũ cho backward compatibility)
        page_index>0 → sub-page (thêm index vào filename)
        """
        if page_index == 0:
            filename = f"{source.category}__{source.name}.txt"
        else:
            # Sub-page: tạo filename từ URL
            url_slug = url_to_filename(url or "")[:60]
            filename = f"{source.category}__{source.name}__{page_index:03d}__{url_slug}.txt"

        filepath = self.output_dir / filename
        metadata = {
            "source_name": source.name,
            "document_title": source.title or source.name,
            "url": url or source.url,
            "parent_url": source.url if page_index > 0 else "",
            "page_index": page_index,
            "category": source.category,
            "language": source.language,
            "source_type": source.source_type,
            "source_priority": source.source_priority,
            "verified_by_doctor": source.verified_by_doctor,
            "published_date": source.published_date,
            "condition_tags": source.condition_tags,
            "crawled_at": datetime.now().isoformat(),
            "char_count": len(text),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("===METADATA===\n")
            f.write(json.dumps(metadata, ensure_ascii=False, indent=2))
            f.write("\n===CONTENT===\n")
            f.write(text)

        return filepath

    # ── Main crawl methods ───────────────────────────────────

    def crawl_source_simple(self, source: MedicalSource, force: bool = False) -> Optional[dict]:
        """
        v1 mode: chỉ crawl đúng 1 URL.
        Dùng khi source.deep_crawl = False.
        """
        filename = f"{source.category}__{source.name}.txt"
        if (self.output_dir / filename).exists() and not force:
            logger.info(f"  ⏭ Đã có: {filename}")
            return {"status": "skipped"}
        if force and (self.output_dir / filename).exists():
            (self.output_dir / filename).unlink()

        logger.info(f"  🌐 Crawl: {source.name} — {source.url}")
        html = self._fetch_html(source.url)
        if not html:
            return {"status": "failed", "source": source.name}

        text = self._extract_text(html, source)
        if not text or len(text) < 200:
            logger.warning(f"  Nội dung quá ngắn: {len(text) if text else 0} ký tự")
            return {"status": "too_short", "source": source.name}

        path = self._save_text(source, text, source.url, 0)
        logger.success(f"  Lưu: {path.name} ({len(text):,} ký tự)")
        return {"status": "success", "source": source.name, "chars": len(text), "pages": 1}

    def crawl_source_deep(self, source: MedicalSource, force: bool = False) -> Optional[dict]:
        """
        v2 mode: BFS crawl với follow links.
        Dùng khi source.deep_crawl = True.

        Thuật toán:
        ─────────────────────────────────────────────────────
        visited = set()   # URLs đã xử lý
        queue = deque([(source.url, 0)])  # (url, depth)

        while queue:
            url, depth = queue.popleft()
            if url in visited: continue
            visited.add(url)

            html = fetch(url)
            text = extract(html)
            save(text)

            if depth < max_depth:
                pdf_links, page_links = extract_links(html)
                for pdf in pdf_links: download_pdf(pdf)
                for page in page_links: queue.append((page, depth+1))
        ─────────────────────────────────────────────────────
        """
        logger.info(f"  🔍 Deep crawl: {source.name} (depth={source.max_depth}, max={source.max_pages})")

        visited: Set[str] = set()
        queue: deque = deque([(normalize_url(source.url), 0)])

        pages_saved = 0
        pdfs_saved = 0
        page_index = 0
        results_detail = []

        while queue and pages_saved < source.max_pages:
            url, depth = queue.popleft()

            if url in visited:
                continue
            visited.add(url)

            logger.deep(f"[depth={depth}] {url[:80]}...")

            # ── Fetch ────────────────────────────────────────
            html = self._fetch_html(url)
            if not html:
                results_detail.append({"url": url, "status": "fetch_failed"})
                continue

            # ── Extract & save text ──────────────────────────
            text = self._extract_text(html, source)
            if text and len(text) >= 200:
                # Kiểm tra đã có file chưa (resume support)
                target_filename = (
                    f"{source.category}__{source.name}.txt"
                    if page_index == 0
                    else f"{source.category}__{source.name}__{page_index:03d}__"
                         f"{url_to_filename(url)[:60]}.txt"
                )
                if force and (self.output_dir / target_filename).exists():
                    (self.output_dir / target_filename).unlink()
                if not (self.output_dir / target_filename).exists():
                    path = self._save_text(source, text, url, page_index)
                    logger.success(f"  ✅ [{page_index}] {path.name} ({len(text):,} ký tự)")
                    pages_saved += 1
                    results_detail.append({"url": url, "status": "saved",
                                           "file": path.name, "chars": len(text)})
                else:
                    logger.info(f"  ⏭ Đã có: {target_filename}")
                    results_detail.append({"url": url, "status": "skipped"})
                page_index += 1
            else:
                logger.warning(f"  ⚠ Nội dung quá ngắn ({len(text) if text else 0} ký tự), bỏ qua text")
                results_detail.append({"url": url, "status": "too_short"})

            # ── Extract links (chỉ khi chưa đạt max depth) ──
            if depth < source.max_depth:
                pdf_links, page_links = self._extract_links(html, url, source)

                # Download PDFs tìm thấy
                for pdf_url in pdf_links:
                    if pages_saved + pdfs_saved >= source.max_pages * 2:
                        break  # Safety limit
                    pdf_path = self._download_pdf(pdf_url, source, force=force)
                    if pdf_path:
                        pdfs_saved += 1
                        results_detail.append({
                            "url": pdf_url, "status": "pdf_downloaded",
                            "file": pdf_path.name
                        })
                    time.sleep(0.5)

                # Queue sub-pages chưa visit
                new_pages = 0
                for page_url in page_links:
                    if page_url not in visited and pages_saved + new_pages < source.max_pages:
                        queue.append((page_url, depth + 1))
                        new_pages += 1

                if pdf_links or page_links:
                    logger.deep(
                        f"  Found: {len(pdf_links)} PDF link, "
                        f"{len(page_links)} sub-page link → queued {new_pages}"
                    )

            # ── Delay lịch sự ────────────────────────────────
            if queue:
                time.sleep(self.delay * 0.5)  # Nhanh hơn một chút cho sub-pages

        # ── Tổng kết ─────────────────────────────────────────
        logger.success(
            f"  Deep crawl '{source.name}' xong: "
            f"{pages_saved} trang, {pdfs_saved} PDF, "
            f"{len(visited)} URLs đã visit"
        )

        return {
            "status": "success" if (pages_saved + pdfs_saved) > 0 else "empty",
            "source": source.name,
            "pages_crawled": pages_saved,
            "pdfs_downloaded": pdfs_saved,
            "urls_visited": len(visited),
            "details": results_detail,
        }

    def crawl_source(self, source: MedicalSource, force: bool = False) -> Optional[dict]:
        """
        Router: chọn mode crawl dựa trên source.deep_crawl.
        """
        if source.deep_crawl:
            return self.crawl_source_deep(source, force=force)
        else:
            return self.crawl_source_simple(source, force=force)

    def crawl_all(self, sources: List[MedicalSource] = None, force: bool = False) -> List[dict]:
        """Crawl tất cả sources."""
        sources = sources or MEDICAL_SOURCES
        logger.section(f"GENERAL CRAWLER v2 — {len(sources)} nguồn")

        # Thống kê quick
        deep_count = sum(1 for s in sources if s.deep_crawl)
        print(f"\n  Mode: {len(sources) - deep_count} simple + {deep_count} deep crawl")

        results = []
        for i, source in enumerate(sources, 1):
            mode_label = "🔍 deep" if source.deep_crawl else "📄 simple"
            print(f"\n  [{i:02d}/{len(sources)}] {mode_label} — {source.name}")
            result = self.crawl_source(source, force=force)
            if result:
                results.append(result)
            if i < len(sources):
                time.sleep(self.delay)

        # ── Thống kê ─────────────────────────────────────────
        success = sum(1 for r in results if r.get("status") == "success")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        failed  = sum(1 for r in results
                      if r.get("status") not in ("success", "skipped", "empty"))
        total_pages = sum(r.get("pages_crawled", 1) for r in results
                          if r.get("status") == "success")
        total_pdfs  = sum(r.get("pdfs_downloaded", 0) for r in results)

        logger.section("KẾT QUẢ GENERAL CRAWLER v2")
        print(f"  ✅ Thành công  : {success} nguồn")
        print(f"  ⏭ Đã có sẵn  : {skipped} nguồn")
        print(f"  ✗ Thất bại    : {failed} nguồn")
        print(f"  📄 Tổng trang  : {total_pages}")
        print(f"  📥 Tổng PDF    : {total_pdfs}")

        meta_path = self.output_dir / "crawl_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "crawled_at": datetime.now().isoformat(),
                "version": "2.0",
                "results": results,
            }, f, ensure_ascii=False, indent=2)

        return results


# ================================================================
# ENTRY POINT
# ================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Healthcare RAG — Medical Document Crawler v2"
    )
    parser.add_argument("--ada-only", action="store_true",
                        help="Chỉ crawl ADA Standards of Care")
    parser.add_argument("--general-only", action="store_true",
                        help="Chỉ crawl các nguồn HTML thông thường")
    parser.add_argument("--demo", action="store_true",
                        help="Demo mode: không download file thật")
    parser.add_argument("--sections", nargs="+", metavar="SECTION_ID",
                        help="ADA: chỉ crawl sections này (vd: s002 s006)")
    parser.add_argument("--sources", nargs="+", metavar="SOURCE_NAME",
                        help="General: chỉ crawl sources này (vd: kcb_quy_trinh...)")
    parser.add_argument("--delay", type=float, default=2.5,
                        help="Giây chờ giữa requests (default: 2.5)")
    parser.add_argument("--no-deep", action="store_true",
                        help="Tắt deep crawl, dùng simple mode cho tất cả")
    args = parser.parse_args()

    print("=" * 60)
    print("  🏥 HEALTHCARE CRAWLER v2 — Deep Crawl Edition")
    print("=" * 60)
    print(f"\n  Output:")
    print(f"    Text → {RAW_DIR.absolute()}")
    print(f"    PDF  → {PDF_DIR.absolute()}")

    if args.demo:
        print("\n  ⚠  DEMO MODE: Không download file thật\n")
    if args.no_deep:
        print("\n  ⚠  --no-deep: Tắt deep crawl cho tất cả sources\n")

    all_results = []

    # ── ADA Crawler ──────────────────────────────────────────
    if not args.general_only:
        ada_crawler = ADAStandardsCrawler(delay=args.delay, demo_mode=args.demo)
        sections_to_crawl = ADA_2026_SECTIONS
        if args.sections:
            sections_to_crawl = [s for s in ADA_2026_SECTIONS
                                  if s.section_id in args.sections]
            if not sections_to_crawl:
                print(f"  ⚠ Không tìm thấy section: {args.sections}")
                print(f"  Hợp lệ: {[s.section_id for s in ADA_2026_SECTIONS]}")
        ada_results = ada_crawler.crawl_all_sections(sections_to_crawl)
        all_results.extend(ada_results)

    # ── General Crawler ──────────────────────────────────────
    if not args.ada_only:
        sources_to_crawl = MEDICAL_SOURCES

        # Lọc theo --sources nếu có
        if args.sources:
            sources_to_crawl = [s for s in MEDICAL_SOURCES
                                 if s.name in args.sources]
            if not sources_to_crawl:
                print(f"  ⚠ Không tìm thấy source: {args.sources}")

        # Override deep_crawl nếu --no-deep
        if args.no_deep:
            for src in sources_to_crawl:
                src.deep_crawl = False

        gen_crawler = HealthcareCrawler(delay=args.delay)
        gen_results = gen_crawler.crawl_all(sources_to_crawl)
        all_results.extend(gen_results)

    # ── Tóm tắt ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  🎉 HOÀN THÀNH")
    total_ok = sum(1 for r in all_results if r.get("status") == "success")
    total_pages = sum(r.get("pages_crawled", 1) for r in all_results
                      if r.get("status") == "success")
    total_pdfs  = sum(r.get("pdfs_downloaded", 0) for r in all_results)
    print(f"  📦 Sources thành công: {total_ok}")
    print(f"  📄 Tổng trang đã lưu : {total_pages}")
    print(f"  📥 Tổng PDF đã tải   : {total_pdfs}")
    print(f"\n  Bước tiếp theo:")
    print(f"    python src/preprocessor/pdf_builder.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
