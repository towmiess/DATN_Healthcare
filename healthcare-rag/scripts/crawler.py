"""
================================================================
CRAWLER v4.2 — Anti-Block Patch
================================================================
FIX SO VỚI v4.1:
  1. [PLAYWRIGHT] Thêm _fetch_with_playwright() làm fallback
     tự động kích hoạt khi requests trả về < 1000B hoặc bị CAPTCHA
     → xử lý được: mayoclinic.org, diabetes.org, diabetes.org.uk,
       healthline.com (CSR), medicalnewstoday.com (CSR), who.int

  2. [WEBMD] Xóa toàn bộ WebMD URLs — bị Cloudflare cứng,
     không crawlable kể cả với Playwright

  3. [DOCKER DNS] Thêm hướng dẫn fix niddk.nih.gov DNS fail
     trong Docker (thêm dns: vào docker-compose.yml)

  4. [SMART RETRY] crawl_url() tự thử Playwright nếu requests fail
     hoặc word_count < 80 — không cần đổi logic gọi

CÁCH DÙNG:
  pip install playwright
  playwright install chromium
  python scripts/crawler.py

DOCKER:
  # Thêm vào docker-compose.yml service rag-api:
  #   dns:
  #     - 8.8.8.8
  #     - 1.1.1.1
  # Rebuild: docker-compose up -d --build
================================================================
"""

import sys
import argparse
import time
import hashlib
import re
import json
import random
import unicodedata
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# ── Cấu hình thư mục ─────────────────────────────────────────
PDF_BASE_DIR = ROOT / "data" / "pdfs"
STATE_FILE   = ROOT / ".crawler_state.json"

# ── Domains cần Playwright (JS-rendered hoặc block requests) ─
PLAYWRIGHT_DOMAINS = {
    "mayoclinic.org",
    "diabetes.org",
    "diabetes.org.uk",
    "who.int",
}

# ── Domains bị block hoàn toàn — skip ngay ───────────────────
# webmd.com: Cloudflare hardblock, không qua được dù Playwright
BLOCKED_DOMAINS = {
    "www.webmd.com",
    "webmd.com",
}
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
window.chrome = { runtime: {} };
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (p) => p.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : originalQuery(p);
"""


def _fetch_with_playwright(url: str) -> Tuple[Optional[bytes], str]:
    if not PLAYWRIGHT_AVAILABLE:
        return None, "playwright_not_installed"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",  # ← quan trọng nhất
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                    "--window-size=1280,800",
                ]
            )
            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                java_script_enabled=True,
                ignore_https_errors=True,
                # Fake device memory và hardware concurrency
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Upgrade-Insecure-Requests": "1",
                }
            )

            # Inject stealth script trước khi load bất kỳ page nào
            context.add_init_script(STEALTH_JS)

            page = context.new_page()

            # Block resource rác
            page.route("**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,otf}",
                       lambda route: route.abort())
            page.route("**/analytics**", lambda route: route.abort())
            page.route("**/gtm**", lambda route: route.abort())
            page.route("**/ads**", lambda route: route.abort())

            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2500)
            except PlaywrightTimeout:
                pass

            content = page.content()
            browser.close()

            if len(content) < 500:
                return None, f"playwright_response_too_short ({len(content)}B)"

            return content.encode("utf-8"), "text/html; charset=utf-8"

    except Exception as e:
        return None, f"playwright_error: {str(e)[:100]}"
    
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# ══════════════════════════════════════════════════════════════
#  CRAWL SOURCES  (WebMD đã xóa hoàn toàn)
# ══════════════════════════════════════════════════════════════
CRAWL_SOURCES: Dict[str, List[Dict]] = {

    "blood_glucose": [
        {"url": "https://www.cdc.gov/diabetes/diabetes-testing/index.html",                                       "title": "Diabetes Testing - CDC",                          "language": "en", "priority": 1},
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/managing-diabetes",               "title": "Managing Diabetes - NIDDK",                       "language": "en", "priority": 1},
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/tests-diagnosis/a1c-test",        "title": "A1C Test - NIDDK",                                "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org/diabetes/a1c",                                                          "title": "A1C - ADA",                                       "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/looking-after-diabetes/hba1c",                        "title": "HbA1c - Diabetes UK",                             "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/looking-after-diabetes/blood-sugar-levels",           "title": "Blood sugar levels",                              "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/looking-after-diabetes/treatments/insulin/resistance", "title": "Insulin resistance",                             "language": "en", "priority": 1},
        {"url": "https://www.vinmec.com/vie/bai-viet/mat-kiem-soat-duong-mau-o-nguoi-dai-thao-duong-vi",         "title": "Mất kiểm soát đường máu",                        "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/theo-doi-duong-mau-nhu-nao-cho-nguoi-benh-dai-thao-duong-vi", "title": "Theo dõi đường máu",                           "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/chi-so-duong-huyet-cua-nguoi-binh-thuong-la-bao-nhieu-vi",  "title": "Chỉ số đường huyết bình thường",                "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/huong-dan-kiem-soat-theo-doi-duong-huyet-tai-nha-vi",       "title": "Hướng dẫn kiểm soát đường huyết tại nhà",        "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/nen-do-duong-huyet-bao-lau-1-lan-vi",                       "title": "Nên đo đường huyết bao lâu 1 lần",               "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/xu-ly-ha-duong-huyet-o-nguoi-tieu-duong-vi",                "title": "Xử lý hạ đường huyết ở người tiểu đường",       "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/duong-huyet-luc-doi-binh-thuong-vi",                        "title": "Đường huyết lúc đói bình thường",                "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/chi-so-tieu-duong-la-gi-khi-nao-ban-can-luu-y-ve-chi-so-tieu-duong", "title": "Chỉ số tiểu đường là gì - Medlatec",           "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/benh-nhan-tieu-duong-nen-do-duong-huyet-bao-lau-1-lan/", "title": "Đo đường huyết bao lâu 1 lần - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/tieu-duong-type-2/chi-so-duong-huyet-an-toan/", "title": "Chỉ số đường huyết an toàn - HelloBacsi",       "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/xet-nghiem-huyet-sac-to-a1c-kiem-tra-benh-tieu-duong", "title": "Xét nghiệm HbA1c - HelloBacsi",           "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/bat-mi-6-thoi-quen-giup-ban-kiem-soat-benh-tieu-duong/", "title": "6 thói quen kiểm soát bệnh tiểu đường - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://www.healthline.com/health/diabetes/how-to-improve-blood-sugar-1-week",                   "title": "Improve blood sugar in 1 week",                   "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/health/blood-sugar-spike",                                            "title": "Blood sugar spike",                               "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/health/hypoglycemia",                                                 "title": "Hypoglycemia - Healthline",                       "language": "en", "priority": 3},
        {"url": "https://www.medicalnewstoday.com/articles/glucose-blood-test",                                   "title": "Glucose blood test",                              "language": "en", "priority": 3},
        {"url": "https://www.medicalnewstoday.com/articles/how-to-prevent-blood-sugar-spikes",                    "title": "Prevent blood sugar spikes",                      "language": "en", "priority": 3},
        {"url": "https://www.medicalnewstoday.com/articles/311240",                                               "title": "What is hypoglycemia",                            "language": "en", "priority": 3},
        # --- CDC Site Index bổ sung ---
        {"url": "https://www.cdc.gov/diabetes/diabetes-testing/prediabetes-a1c-test.html", "title": "A1C Test for Diabetes and Prediabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-testing/monitoring-blood-sugar.html", "title": "Monitoring Your Blood Sugar - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/treatment/continuous-glucose-monitors.html", "title": "Continuous Glucose Monitors - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/living-with/10-things-that-spike-blood-sugar.html", "title": "10 Things That Can Spike Blood Sugar - CDC", "language": "en", "priority": 1},
        # --- diabetes.co.uk bổ sung ---
        {"url": "https://www.diabetes.co.uk/blood-glucose/blood-glucose-testing.html", "title": "Blood glucose testing overview - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes_care/blood_glucose_monitor_guide.html", "title": "Blood glucose meter guide - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes_care/diabetes-test-strips.html", "title": "Blood glucose test strips - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/cgm/continuous-glucose-monitoring.html", "title": "Continuous glucose monitoring - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/glucose-intolerance.html", "title": "Glucose intolerance - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/blood-glucose/how-to-test-blood-glucose-levels.html", "title": "How to test your blood glucose - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-ketones.html", "title": "Ketones - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes_care/testing-for-ketones.html", "title": "Ketone testing - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/blood-glucose/ketosis.html", "title": "Ketosis - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes_care/blood-sugar-level-ranges.html", "title": "Blood glucose level ranges - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes_care/fasting-blood-sugar-levels.html", "title": "Fasting blood glucose levels - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/what-is-hba1c.html", "title": "HbA1c - Diabetes.co.uk", "language": "en", "priority": 2},
    ],

    "diagnosis": [
        {"url": "https://www.cdc.gov/diabetes/signs-symptoms/index.html",                                         "title": "Diabetes Signs & Symptoms - CDC",                 "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/basics/type2.html",                                                 "title": "Type 2 Diabetes Basics - CDC",                    "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/basics/type1.html",                                                 "title": "Type 1 Diabetes Basics - CDC",                    "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/basics/prediabetes.html",                                           "title": "Prediabetes - CDC",                               "language": "en", "priority": 1},
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/what-is-diabetes",                "title": "What Is Diabetes - NIDDK",                        "language": "en", "priority": 1},
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/symptoms-causes",                 "title": "Symptoms & Causes - NIDDK",                       "language": "en", "priority": 1},
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/tests-diagnosis",                 "title": "Tests & Diagnosis - NIDDK",                       "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org/diabetes/a1c",                                                          "title": "A1C and Diagnosis - ADA",                         "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/type-1-diabetes/symptoms",                            "title": "Type 1 symptoms",                                 "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/type-1-diabetes/causes",                              "title": "Type 1 causes",                                   "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/type-2-diabetes/symptoms",                            "title": "Type 2 symptoms",                                 "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/type-2-diabetes/causes",                              "title": "Type 2 causes",                                   "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/type-2-diabetes/prediabetes",                         "title": "Prediabetes overview",                            "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/test-for-diabetes",                                   "title": "Test for diabetes",                               "language": "en", "priority": 1},
        {"url": "https://www.who.int/news-room/fact-sheets/detail/diabetes",                                      "title": "Diabetes Fact Sheet - WHO",                       "language": "en", "priority": 1},
        {"url": "https://www.vinmec.com/vie/bai-viet/tieu-chuan-chan-doan-dai-thao-duong-va-tien-dai-thao-duong-vi", "title": "Tiêu chuẩn chẩn đoán ĐTĐ",                   "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/dai-thao-duong-co-may-tuyp-su-khac-nhau-giua-cac-tuyp-la-gi-vi", "title": "ĐTĐ có mấy tuýp",                           "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/ai-co-nguy-co-cao-bi-dai-thao-duong-vi",                    "title": "Ai có nguy cơ cao bị ĐTĐ",                       "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/tong-quan-ve-benh-dai-thao-duong-vi",                       "title": "Tổng quan về bệnh đái tháo đường",               "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/tien-dai-thao-duong-nhung-dieu-can-biet-vi",                "title": "Tiền đái tháo đường - những điều cần biết",      "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/dau-hieu-som-bao-hieu-benh-tieu-duong-vi",                  "title": "Dấu hiệu sớm bệnh tiểu đường",                  "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/dai-thao-duong-trieu-chung-nguyen-nhan-va-cach-phong-ngua",         "title": "ĐTĐ triệu chứng nguyên nhân phòng ngừa",        "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/benh-dai-thao-duong-va-nhung-kien-thuc-co-ban-ai-cung-nen-biet-s62-n33632", "title": "Bệnh ĐTĐ kiến thức cơ bản - Medlatec",   "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/tieu-duong-type-2/chan-doan-tieu-duong-tuyp-2/", "title": "Chẩn Đoán Tiểu Đường Type 2 - HelloBacsi",    "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/tieu-duong/",                                   "title": "Tiểu đường tổng quan - HelloBacsi",              "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/tieu-chuan-chan-doan-tieu-duong/",              "title": "Tiêu chuẩn chẩn đoán tiểu đường - HelloBacsi",  "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/tieu-duong-type-2/benh-tieu-duong-tuyp-2/",    "title": "Tiểu đường tuýp 2 là gì - HelloBacsi",          "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/khi-mac-benh-tieu-duong/",                     "title": "Phân biệt tiểu đường tuýp 1 và tuýp 2 - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://www.healthline.com/health/type-2-diabetes/diagnosis",                                    "title": "Type 2 diabetes diagnosis",                       "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/health/type-3-diabetes",                                              "title": "Type 3 diabetes",                                 "language": "en", "priority": 3},
        {"url": "https://www.medicalnewstoday.com/articles/322919",                                               "title": "Type 2 diabetes overview",                        "language": "en", "priority": 3},
        {"url": "https://www.medicalnewstoday.com/articles/249413",                                               "title": "Type 1 diabetes overview",                        "language": "en", "priority": 3},
        {"url": "https://www.medicalnewstoday.com/articles/325177",                                               "title": "Prediabetes",                                     "language": "en", "priority": 3},

        # --- CDC Site Index bổ sung ---
        {"url": "https://www.cdc.gov/diabetes/signs-symptoms/just-diagnosed-type-1.html", "title": "Just Diagnosed With Type 1 Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/signs-symptoms/coping-with-type-2-diagnosis.html", "title": "Coping With a Type 2 Diabetes Diagnosis - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-testing/screening-type-1-diabetes.html", "title": "Screening for Type 1 Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/data-research/research/diabetes-screening-eligible.html", "title": "12 Million More Adults Eligible for Diabetes Screening - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/communication-resources/prediabetes-statistics.html", "title": "Prediabetes: Could It Be You? - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/awareness-campaigns/prediabetes-awareness-campaign.html", "title": "Do I Have Prediabetes Campaign - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/awareness-campaigns/cdc-national-prediabetes-awareness-campaign.html", "title": "First National Prediabetes Awareness Campaign - CDC", "language": "en", "priority": 1},
        # --- diabetes.co.uk bổ sung ---
        {"url": "https://www.diabetes.co.uk/diabetes-symptoms.html", "title": "Symptoms of diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/type1-diabetes-symptoms.html", "title": "Type 1 diabetes symptoms - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/type2-diabetes-symptoms.html", "title": "Type 2 diabetes symptoms - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-types.html", "title": "Types of diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/type1-diabetes.html", "title": "Type 1 diabetes overview - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/newly-diagnosed-with-type1-diabetes.html", "title": "Newly diagnosed with Type 1 - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/causes-of-type1-diabetes.html", "title": "Causes of type 1 diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/pre-diabetes.html", "title": "Prediabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/Diabetes-Risk-factors.html", "title": "Diabetes risk factors - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/skinny-type2-diabetes.html", "title": "Lean type 2 diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/newly-diagnosed-with-type2-diabetes.html", "title": "Newly diagnosed with type 2 - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/causes-of-type2-diabetes.html", "title": "Causes of type 2 diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
    ],

    "diet": [
        {"url": "https://www.diabetes.org/healthy-living/recipes-nutrition/eating-well",                          "title": "Eating Well - ADA",                               "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org/healthy-living/recipes-nutrition/understanding-carbs",                  "title": "Understanding Carbs - ADA",                       "language": "en", "priority": 1},
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/diet-eating-physical-activity",   "title": "Diabetes Diet - NIDDK",                           "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/type-2-diabetes/prevention/healthy-eating-tips-to-lower-type-2-risk", "title": "Healthy eating tips type 2",     "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/living-with-diabetes/eating/i-have-type-1-diabetes",                "title": "Eating guide type 1",                             "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/living-with-diabetes/eating/i-have-type-2-diabetes",                "title": "Eating guide type 2",                             "language": "en", "priority": 1},
        {"url": "https://www.vinmec.com/vie/bai-viet/dinh-duong-trong-benh-dai-thao-duong-vi",                   "title": "Dinh dưỡng trong bệnh ĐTĐ",                      "language": "vi", "priority": 2},
        {"url": "https://nutrihome.vn/trai-cay-danh-cho-nguoi-tieu-duong/",                                      "title": "20 loại trái cây dành cho người tiểu đường và lưu ý khi ăn", "language": "vi", "priority": 2},
        {"url": "https://nutricare.com.vn/16-loai-trai-cay-tot-cho-benh-tieu-duong-6-loai-trai-cay-kieng-an-can-tranh/", "title": "16 +loại trái cây tốt cho bệnh tiểu đường & 6 loại trái cây kiêng ăn cần tránh", "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/dinh-duong-trong-dieu-tri-dai-thao-duong",                  "title": "Dinh dưỡng trong điều trị ĐTĐ",                  "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/nguoi-bi-tieu-duong-tuyp-2-nen-an-gi-de-cai-thien-benh-s62-n27831", "title": "Tiểu đường type 2 nên ăn gì - Medlatec",        "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/goi-y-danh-sach-nhung-loai-trai-cay-danh-cho-nguoi-tieu-duong-s51-n30092", "title": "Gợi ý danh sách những loại trái cây dành cho người tiểu đường", "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/vitamin-va-khoang-chat-tren-benh-nhan-dai-thao-duong-tuyp-2-vi", "title": "Vitamin và khoáng chất trên bệnh nhân đái tháo đường tuýp 2", "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/che-do-an-cua-nguoi-tieu-duong-chuan-theo-huong-dan-cua-bac-si-s62-n29226", "title": "Chế độ ăn tiểu đường chuẩn",              "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/top-15-thuc-pham-kiem-soat-benh-tieu-duong-tot-nhat/", "title": "15 thực phẩm kiểm soát tiểu đường - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/tieu-duong-type-2/che-do-an-danh-cho-nguoi-bi-tieu-duong-type-2/", "title": "Chế độ ăn tiểu đường type 2 - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/kiem-soat-benh-tieu-duong-voi-chi-so-duong-huyet-o-thuc-pham/", "title": "Thực phẩm GI thấp cho tiểu đường - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/bua-sang-cho-nguoi-tieu-duong/",               "title": "Bữa sáng cho người tiểu đường - HelloBacsi",      "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/benh-dai-thao-duong-che-do-nhu-nao-vi", "title": "Bệnh đái tháo đường: chế độ ăn như thế nào?", "language": "vi", "priority": 2},
        {"url": "https://www.healthline.com/nutrition/foods-to-avoid-with-diabetes",                              "title": "Foods to avoid with diabetes",                    "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/nutrition/16-best-foods-for-diabetics",                               "title": "Best foods for diabetics",                        "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/nutrition/low-carb-diet-for-diabetes",                                "title": "Low carb diet for diabetes",                      "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/health/diabetes/breakfast-ideas",                                     "title": "Breakfast ideas for diabetes",                    "language": "en", "priority": 3},
        {"url": "https://www.medicalnewstoday.com/articles/317536",                                               "title": "Diet for type 2 diabetes",                        "language": "en", "priority": 3},
        {"url": "https://www.medicalnewstoday.com/articles/318727",                                               "title": "Best drinks for diabetics",                       "language": "en", "priority": 3},
        # --- CDC Site Index bổ sung ---
        {"url": "https://www.cdc.gov/diabetes/healthy-eating/diabetes-meal-planning.html", "title": "Diabetes Meal Planning - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/healthy-eating/carb-counting-manage-blood-sugar.html", "title": "Carb Counting - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/healthy-eating/carbohydrate-lists-starchy-foods.html", "title": "Carbohydrate Choice Lists - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/healthy-eating/eating-out.html", "title": "Eating Out - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/healthy-eating/people-with-diabetes-dessert.html", "title": "Can People With Diabetes Have Dessert? - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/healthy-eating/5-healthy-eating-tips-holidays.html", "title": "5 Healthy Eating Tips for the Holidays - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/healthy-eating/diabetes-cultural-foods.html", "title": "Diabetes and Cultural Foods - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/healthy-eating/diabetes-and-cancer-what-to-eat.html", "title": "Healthy Eating with Diabetes and Cancer - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/healthy-eating/diabetes-and-kidney-disease-food.html", "title": "Diabetes & Kidney Disease: What to Eat? - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/healthy-eating/fiber-helps-diabetes.html", "title": "Diabetes and Fiber Intake - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/healthy-eating/diabetes-food-insecurity.html", "title": "Diabetes and Food Insecurity - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/healthy-eating/6-tips-eating-healthy-on-budget.html", "title": "6 Tips for Eating Healthy on a Budget - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/healthy-eating/choosing-healthy-foods-holidays.html", "title": "Buffet Table Tips for People With Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/healthy-eating/choosing-healthy-carbs.html", "title": "Choosing Healthy Carbs - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/healthy-eating/spotting-hidden-sugars-in-everyday-foods.html", "title": "Spotting Hidden Sugars in Everyday Foods - CDC", "language": "en", "priority": 1},
        # --- diabetes.co.uk bổ sung ---
        {"url": "https://www.diabetes.co.uk/diet-for-type1-diabetes.html", "title": "Diet for type 1 diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diet-for-type2-diabetes.html", "title": "Diet for type 2 diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/food/which-foods-help-diabetes.html", "title": "Blood glucose friendly foods - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetic-food.html", "title": "Diabetic food - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diet-basics.html", "title": "Diet guides overview - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diet/nhs-diet-advice.html", "title": "NHS diet advice - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diet/newcastle-study-600-calorie-diet", "title": "800 calorie shake diet - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diet/fasting-and-diabetes.html", "title": "Fasting and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diet/glycaemic-index-diet-and-diabetes.html", "title": "Glycemic index - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/keto/", "title": "Ketogenic diet - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diet/low-calorie-diets.html", "title": "Low calorie diet - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diet/low-carb-diabetes-diet.html", "title": "Low carb diet - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diet/mediterranean-diet.html", "title": "Mediterranean diet - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diet/paleolithic-diet.html", "title": "Paleo diet - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diet/very-low-calorie-diet.html", "title": "Very low calorie diet - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diet/vegan-diet.html", "title": "Vegan diet - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/vegetarian-diet.html", "title": "Vegetarian diet - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/food/diabetic-breakfast.html", "title": "Breakfast ideas - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/food/low-carb-lunch.html", "title": "Lunch ideas - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/food/low-carb-dinner.html", "title": "Dinner ideas - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diet/ramadan-and-diabetes.html", "title": "Ramadan and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/food/what-can-i-drink.html", "title": "Drinks overview - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-alcohol.html", "title": "Alcohol and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/sweeteners/sugar-alcohols.html", "title": "Sugar alcohols - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/alcohol-and-blood-sugar.html", "title": "Alcohol and blood sugar - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/food/coffee-and-diabetes.html", "title": "Coffee and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diet-soft-drinks.html", "title": "Diet soft drinks - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/food/juice-and-diabetes.html", "title": "Fruit juice and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/food/tea-and-diabetes.html", "title": "Tea and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/sports-drinks.html", "title": "Sports drinks - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/sugary-soft-drinks.html", "title": "Sugary soft drinks - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/nutrition.html", "title": "Nutrition overview - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes_care/Diabetes_and_low_calorie_sweeteners.html", "title": "Artificial sweeteners - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/nutrition/carbohydrates-and-diabetes.html", "title": "Carbohydrates and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diet/carbohydrate-counting.html", "title": "Carb counting - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/nutrition/simple-carbs-vs-complex-carbs.html", "title": "Simple vs complex carbs - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/nutrition/dietary-supplements.html", "title": "Dietary supplements - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/nutrition/fat-and-diabetes.html", "title": "Fat and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/nutrition/sugar-vs-fat.html", "title": "Sugar vs fat - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/food/food-diary.html", "title": "Food diary - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/Food-tips-for-diabetics.html", "title": "Food tips for diabetics - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/food/fruit.html", "title": "Fruit and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/portion-control.html", "title": "Portion control - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/food/processed-foods.html", "title": "Processed foods - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/nutrition/protein-and-diabetes.html", "title": "Protein and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/nutrition/sugar.html", "title": "Sugar and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/vitamins-supplements.html", "title": "Vitamins and minerals - Diabetes.co.uk", "language": "en", "priority": 2},
    ],

    "emergency": [
        {"url": "https://www.cdc.gov/diabetes/treatment/low-blood-sugar.html",                                    "title": "Low Blood Sugar Treatment - CDC",                 "language": "en", "priority": 1},
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/low-blood-glucose-hypoglycemia", "title": "Hypoglycemia - NIDDK",       "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org/diabetes/complications/dka-ketoacidosis-ketones",                       "title": "DKA - ADA",                                       "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/looking-after-diabetes/treatments/insulin/accidental-overdose", "title": "Insulin accidental overdose",         "language": "en", "priority": 1},
        {"url": "https://www.vinmec.com/vie/bai-viet/phat-hien-ha-duong-huyet-o-nguoi-benh-dai-thao-vi",         "title": "Phát hiện hạ đường huyết",                       "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/xu-ly-ha-duong-huyet-o-nguoi-tieu-duong-vi",                "title": "Xử lý hạ đường huyết ở người tiểu đường",       "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/hay-ha-duong-huyet-co-phai-bi-tieu-duong-vi",               "title": "Hạ đường huyết có phải bị tiểu đường",          "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/thuoc-chong-bien-chung-tieu-duong-phan-loai-va-luu-y-su-dung-s62-n33463", "title": "Thuốc chống biến chứng tiểu đường",         "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/bien-chung-tieu-duong/bien-chung-cap-tinh-cua-benh-tieu-duong/", "title": "Biến chứng cấp tính - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/bien-chung-tieu-duong/benh-tieu-duong-nguy-hiem-nhu-the-nao/", "title": "Bệnh tiểu đường nguy hiểm - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://www.medicalnewstoday.com/articles/320739",                                               "title": "Hypoglycemia - MNT",                              "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/health/hypoglycemia",                                                 "title": "Hypoglycemia - Healthline",                       "language": "en", "priority": 3},

        # --- CDC Site Index bổ sung ---
        {"url": "https://www.cdc.gov/diabetes/about/diabetic-ketoacidosis.html", "title": "Diabetic Ketoacidosis - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/about/low-blood-sugar-hypoglycemia.html", "title": "Low Blood Sugar (Hypoglycemia) - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/treatment/treatment-low-blood-sugar-hypoglycemia.html", "title": "Treatment for Low Blood Sugar - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/articles/managing-insulin-in-emergency.html", "title": "Managing Insulin in an Emergency - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/articles/diabetes-care-emergencies.html", "title": "Diabetes Care During Emergencies - CDC", "language": "en", "priority": 1},
        # --- diabetes.co.uk bổ sung ---
        {"url": "https://www.diabetes.co.uk/diabetes-complications/diabetic-ketoacidosis.html", "title": "Diabetic ketoacidosis (DKA) - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/Diabetes-and-Hypoglycaemia.html", "title": "Hypoglycemia (low blood glucose) - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/how-to/treat-a-hypo.html", "title": "How to treat a hypo - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/Diabetes-and-Hyperglycaemia.html", "title": "Hyperglycemia (high blood glucose) - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/how-to/bring-down-high-blood-sugar-levels.html", "title": "How to bring down high blood sugar - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-complications/hyperosmolar-hyperglycemic-nonketotic-syndrome.html", "title": "Hyperosmolar hyperglycemic nonketotic syndrome - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/nocturnal-hypoglycemia.html", "title": "Nocturnal hypoglycemia - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-complications/diabetic-coma.html", "title": "Diabetic coma - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/alcohol-and-hypoglycemia.html", "title": "Alcohol and hypoglycemia - Diabetes.co.uk", "language": "en", "priority": 2},
    ],

    "general": [
        {"url": "https://www.who.int/news-room/fact-sheets/detail/diabetes",                                      "title": "Diabetes Fact Sheet - WHO",                       "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/basics/index.html",                                                 "title": "Diabetes Basics - CDC",                           "language": "en", "priority": 1},
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview",                                 "title": "Diabetes Overview - NIDDK",                       "language": "en", "priority": 1},
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems",             "title": "Preventing Diabetes Problems - NIDDK",            "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org/diabetes/complications",                                                "title": "Diabetes Complications - ADA",                    "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/looking-after-diabetes/complications",                "title": "Diabetes complications overview",                 "language": "en", "priority": 1},
        {"url": "https://www.vinmec.com/vie/bai-viet/tong-quan-ve-benh-dai-thao-duong-vi",                       "title": "Tổng quan về bệnh ĐTĐ",                          "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/bien-chung-tren-benh-nhan-dai-thao-duong-vi",               "title": "Biến chứng trên bệnh nhân ĐTĐ",                 "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/benh-dai-thao-duong-can-ban-va-cap-nhat-vi",                "title": "Bệnh ĐTĐ căn bản và cập nhật",                  "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/benh-dai-thao-duong-va-nhung-kien-thuc-co-ban-ai-cung-nen-biet-s62-n33632", "title": "Bệnh ĐTĐ kiến thức cơ bản",              "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/nhung-bien-chung-cua-benh-tieu-duong-ban-nen-biet-de-phong-ngua",   "title": "Biến chứng bệnh tiểu đường - Medlatec",          "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/cac-bien-chung-cua-benh-tieu-duong-tuyet-doi-khong-chu-quan",       "title": "Các biến chứng ĐTĐ không chủ quan",             "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/tieu-duong/",                                   "title": "Tiểu Đường Là Gì - HelloBacsi",                  "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/bien-chung-tieu-duong/benh-tieu-duong-nguy-hiem-nhu-the-nao/", "title": "Bệnh tiểu đường nguy hiểm - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/tieu-duong-type-2/dai-thao-duong-tip-2-co-nguy-hiem-khong/", "title": "Tiểu đường type 2 có nguy hiểm không - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://www.healthline.com/health/diabetes",                                                     "title": "Diabetes overview - Healthline",                  "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/health/diabetes/effects-on-body",                                     "title": "How diabetes affects your body",                  "language": "en", "priority": 3},
        {"url": "https://www.medicalnewstoday.com/articles/317168",                                               "title": "Diabetes complications overview",                 "language": "en", "priority": 3},
        {"url": "https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444",           "title": "Diabetes overview - Mayo",                       "language": "en", "priority": 2},
        # --- CDC Site Index bổ sung ---
        {"url": "https://www.cdc.gov/diabetes/about/about-type-1-diabetes.html", "title": "About Type 1 Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/about/about-type-2-diabetes.html", "title": "About Type 2 Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/about/type-1-teen-adult.html", "title": "Make the Leap From Type 1 Teen to Adult - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/signs-symptoms/diabetes-and-your-skin.html", "title": "Diabetes and Your Skin - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/risk-factors/pcos-polycystic-ovary-syndrome.html", "title": "Diabetes and PCOS - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/risk-factors/diabetes-and-smoking.html", "title": "Diabetes and Smoking - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/risk-factors/diabetes-and-men.html", "title": "Diabetes and Men - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/risk-factors/diabetes-and-women-1.html", "title": "Diabetes and Women - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/risk-factors/diabetes-risk-lgbtq.html", "title": "Diabetes and the LGBTQ Community - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/treatment/diabetes-doctors.html", "title": "Your Diabetes Care Team - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/treatment/your-diabetes-care-schedule.html", "title": "Your Diabetes Care Schedule - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/caring/3-ways-help-manage-childs-type-1.html", "title": "3 Ways to Manage Your Child's Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/caring/managing-diabetes-at-school.html", "title": "Managing Diabetes at School - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/caring/help-diabetes-when-you-live-apart.html", "title": "Help a Loved One With Diabetes When Far Apart - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/caring/5-questions-health-care-team.html", "title": "5 Questions to Ask Your Health Care Team - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/caring/steps-to-help-you-stay-healthy-with-diabetes.html", "title": "Steps to Help You Stay Healthy With Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/living-with/mental-health.html", "title": "Diabetes and Mental Health - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/living-with/managing-sick-days.html", "title": "Managing Sick Days - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/health-equity/improving-access-education.html", "title": "Improving Access to Diabetes Education - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/health-equity/improving-health-appalachia.html", "title": "Improving Health in Appalachia - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/health-equity/health-american-indian.html", "title": "Improving Health in Indian Country - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/data-research/research/treatment-goals.html", "title": "How People with Type 2 Diabetes Can Live Longer - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/data-research/research/diabetes-education.html", "title": "Diabetes Education Linked to Better Care - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/data-research/research/young-people-mental-health.html", "title": "Mental Health for Kids and Teens With Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/data-research/research/older-adults.html", "title": "Cost of Diabetes Complications for Medicare Beneficiaries - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/data-research/research/young-people-diabetes-on-rise.html", "title": "Diabetes in Young People Is on the Rise - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/data-research/research/trends-new-diabetes-cases-young-people.html", "title": "Trends in Diabetes Among Young People - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/communication-resources/diabetes-statistics.html", "title": "A Report Card: Diabetes In The United States - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/communication-resources/how-diabetes-can-affect-your-body.html", "title": "How Diabetes Can Affect Your Body - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/communication-resources/social-media-graphics.html", "title": "Social Media Graphics - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/communication-resources/diabetes-complications-social-media-graphics.html", "title": "Diabetes Complications Social Media Graphics - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/communication-resources/2-in-5-americans.html", "title": "2 in 5 Americans - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-complications/diabetes-and-hearing-loss.html", "title": "Hearing Loss - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-complications/diabetes-and-oral-health.html", "title": "Oral Health - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-complications/diabetes-and-digestion.html", "title": "Digestion and Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-complications/type-2-diabetes-liver-disease.html", "title": "Type 2 Diabetes and Your Liver - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-complications/diabetes-immune-system.html", "title": "Your Immune System and Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-complications/effects-of-diabetes-brain.html", "title": "Your Brain and Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-tv/your-health-with-joan-lunden.html", "title": "Your Health With Joan Lunden Video Series - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/education-support-programs/find-a-dsmes-program.html", "title": "Find a DSMES Program - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/articles/the-diabetes-journey-to-purpose.html", "title": "The Diabetes Journey to Purpose - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/articles/healthy-family-kids.html", "title": "Healthy on the Inside - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/articles/diabetes-stigma.html", "title": "Diabetes Stigma - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/articles/10-tips-coping-diabetes-distress.html", "title": "10 Tips for Coping with Diabetes Distress - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/articles/diabetes-and-hormonal-birth-control.html", "title": "Diabetes and Hormonal Birth Control - CDC", "language": "en", "priority": 1},
        # --- diabetes.co.uk bổ sung ---
        {"url": "https://www.diabetes.co.uk/having-diabetes.html", "title": "Having diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-life.html", "title": "Living with diabetes overview - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/type2-diabetes.html", "title": "Type 2 diabetes overview - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/kids/type-1-diabetes-and-children.html", "title": "Type 1 diabetes in children - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/nhs/diabetes-health-checks.html", "title": "Annual diabetes checks - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-discrimination.html", "title": "Discrimination - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/driving-with-diabetes.html", "title": "Driving with diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-illness.html", "title": "Illness and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/flu-and-diabetes.html", "title": "Flu and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-life-expectancy.html", "title": "Life expectancy - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/emotions/", "title": "Mental health overview - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-depression.html", "title": "Depression - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-destress.html", "title": "Managing stress - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/recreational-drugs/index.html", "title": "Recreational drugs - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-sex.html", "title": "Sex and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/features/diabetes-and-sexual-health.html", "title": "Sexual health - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/beating-sexual-problems.html", "title": "Beating sexual problems - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/Diabetes-Impotence-and-Sexual-Dysfunction.html", "title": "Impotence - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-skin-care.html", "title": "Skin care - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-smoking.html", "title": "Smoking - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/how-does-diabetes-affect-the-body.html", "title": "How diabetes affects the body - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/embarrassing-conditions.html", "title": "Embarrassing conditions overview - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/conditions/diabetes-and-constipation.html", "title": "Constipation - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/conditions/diabetic-diarrhoea.html", "title": "Diarrhoea - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-erectile-dysfunction.html", "title": "Erectile dysfunction - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/conditions/hayfever-and-seasonal-allergies.html", "title": "Hay fever - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/Diabetes-and-Nocturia.html", "title": "Nocturia - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-complications/diabetes-and-yeast-infections.html", "title": "Thrush - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-complications/urinary-tract-infections.html", "title": "UTIs - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-complications/short-term-complications.html", "title": "Short term complications overview - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-complications/muscle-cramp-and-diabetes.html", "title": "Muscle cramps - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-complications/edema-and-diabetes.html", "title": "Swelling - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/emotions/fear-of-long-term-diabetes-complications.html", "title": "Long term complications overview - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/conditions/alzheimers-and-diabetes.html", "title": "Alzheimer's disease - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/binge-eating-disorders.html", "title": "Binge eating - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-complications/diabetes-and-cancer.html", "title": "Cancer guide - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-coeliac.html", "title": "Coeliac disease - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-complications/diabetes-and-fatty-liver-disease.html", "title": "Non-alcoholic fatty liver disease - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/conditions/polycystic-ovary-syndrome.html", "title": "Polycystic ovary syndrome - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/caring-for-someone-with-diabetes.html", "title": "Caring for someone with diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-the-elderly.html", "title": "Caring for the elderly - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-parenting.html", "title": "Parenting a child with diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-employment.html", "title": "Diabetes and employment - Diabetes.co.uk", "language": "en", "priority": 2},
    ],

    "lifestyle": [
        {"url": "https://www.cdc.gov/diabetes/living-with/index.html",                                            "title": "Living with Diabetes - CDC",                      "language": "en", "priority": 1},
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/diet-eating-physical-activity",   "title": "Physical Activity - NIDDK",                       "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org/healthy-living/fitness",                                                "title": "Fitness - ADA",                                   "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org/healthy-living/mental-health",                                          "title": "Mental Health - ADA",                             "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/type-2-diabetes/remission",                          "title": "Type 2 remission",                                "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/living-with-diabetes/emotional-wellbeing",                           "title": "Emotional wellbeing",                             "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/living-with-diabetes/exercise",                                      "title": "Exercise with diabetes",                          "language": "en", "priority": 1},
        {"url": "https://www.vinmec.com/vie/bai-viet/stress-va-dai-thao-duong-vi",                               "title": "Stress và ĐTĐ",                                  "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/tieu-duong-type-2/cach-dieu-tri-benh-tieu-duong-giai-doan-dau/", "title": "Điều trị tiểu đường giai đoạn đầu - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/bat-mi-6-thoi-quen-giup-ban-kiem-soat-benh-tieu-duong/", "title": "6 thói quen kiểm soát tiểu đường - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/chuyen-de/tieu-duong-dai-thao-duong/tap-the-duc-giup-kiem-soat-duong-huyet/", "title": "Tập thể dục kiểm soát đường huyết - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/tieu-duong-type-2/kiem-soat-tieu-duong-tuyp-2/", "title": "Kiểm soát tiểu đường tuýp 2 - HelloBacsi",     "language": "vi", "priority": 2},
        {"url": "https://www.healthline.com/health/type-2-diabetes/top-exercises",                                "title": "Top exercises for type 2 diabetes",               "language": "en", "priority": 3},
        {"url": "https://www.medicalnewstoday.com/articles/317224",                                               "title": "Exercise for diabetes",                           "language": "en", "priority": 3},
        {"url": "https://www.medicalnewstoday.com/articles/317468",                                               "title": "Lifestyle management diabetes",                   "language": "en", "priority": 3},
        {"url": "https://www.mayoclinic.org/diseases-conditions/diabetes/in-depth/diabetes-and-exercise/art-20045697", "title": "Diabetes and exercise - Mayo",              "language": "en", "priority": 2},
        # --- CDC Site Index bổ sung ---
        {"url": "https://www.cdc.gov/diabetes/about/tips-for-traveling-with-diabetes.html", "title": "Tips for Traveling With Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/prevention-type-2/prediabetes-prevent-type-2.html", "title": "Prediabetes - Your Chance to Prevent Type 2 - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/prevention-type-2/type-2-diabetes-in-kids.html", "title": "Type 2 Diabetes in Kids - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/prevention-type-2/type-2-diabetes-prevention-guide.html", "title": "On Your Way to Preventing Type 2 Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/prevention-type-2/truth-about-prediabetes.html", "title": "The Surprising Truth About Prediabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/prevention-type-2/building-a-healthy-habit.html", "title": "3 Steps to Building a Healthy Habit - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/prevention-type-2/reaching-goals.html", "title": "Change Negative Thoughts to Reach Goals - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/prevention-type-2/new-healthy-habits.html", "title": "Fitting a New Habit into Your Life - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/prevention-type-2/stop-diabetes-complications.html", "title": "Put the Brakes on Diabetes Complications - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/living-with/healthy-weight.html", "title": "Healthy Weight - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/living-with/physical-activity.html", "title": "Get Active - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/health-equity/improving-access-type-2-diabetes-prevention-program.html", "title": "Improving Access to Diabetes Prevention - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/communication-resources/ndpp-prevent-type-2-diabetes.html", "title": "National Diabetes Prevention Program Infographic - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/communication-resources/3-steps-healthy-habits.html", "title": "3 Steps to Building Healthy Habits - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-tv/diabetes-kickstart.html", "title": "Diabetes Kickstart Video Series - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-tv/kickstart-handouts.html", "title": "Diabetes Kickstart Handouts - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-tv/imagine-you-preventing-type-2.html", "title": "Imagine You Preventing Type 2 Videos - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/articles/weight-loss-stories.html", "title": "Weight Loss: What Works for Me - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/articles/diabetes-shift-work.html", "title": "Diabetes and Shift Work - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/articles/weight-loss-story.html", "title": "Lost 170 Pounds and Regained His Life - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/articles/managing-diabetes-in-the-heat.html", "title": "Managing Diabetes in the Heat - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/articles/managing-diabetes-cold-weather.html", "title": "Managing Diabetes in Cold Weather - CDC", "language": "en", "priority": 1},
        # --- diabetes.co.uk bổ sung ---
        {"url": "https://www.diabetes.co.uk/controlling-type1-diabetes.html", "title": "Controlling type 1 diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/controlling-type2-diabetes.html", "title": "Controlling type 2 diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/reversing-diabetes.html", "title": "Reversing type 2 diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/body-piercing-and-diabetes.html", "title": "Body piercing and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-cold-weather.html", "title": "Cold weather and diabetes management - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-hot-weather.html", "title": "Hot weather and diabetes management - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/tattoos-and-diabetes.html", "title": "Tattoos and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-keeping-active.html", "title": "Keeping active overview - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/exercise-for-diabetics.html", "title": "Exercise - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/gym-and-diabetes.html", "title": "Going to the gym - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/healthy-lifestyle.html", "title": "Healthy lifestyle - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-sport.html", "title": "Sport and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/Diabetes-and-Weight-Loss.html", "title": "Weight loss - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/travel-guides/", "title": "Travelling with diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
    ],

    "medication": [
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/insulin-medicines-treatments",    "title": "Diabetes Medicines - NIDDK",                      "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/type-1-diabetes/treatments",                          "title": "Type 1 treatments",                               "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/type-2-diabetes/treatments",                          "title": "Type 2 treatments",                               "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/looking-after-diabetes/treatments/insulin/what-is-insulin", "title": "What is insulin",                         "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/looking-after-diabetes/treatments/insulin/types",     "title": "Types of insulin",                                "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/looking-after-diabetes/treatments/insulin/side-effects", "title": "Insulin side effects",                       "language": "en", "priority": 1},
        {"url": "https://www.vinmec.com/vie/bai-viet/thuoc-dieu-tri-dai-thao-duong-type-2-vi",                   "title": "Thuốc điều trị ĐTĐ type 2",                     "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/cac-nhom-thuoc-dieu-tri-dai-thao-duong-vi",                 "title": "Các nhóm thuốc điều trị ĐTĐ",                   "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/benh-nhan-dai-thao-duong-tiem-insulin-khi-nao-vi",          "title": "Bệnh nhân ĐTĐ tiêm insulin khi nào",            "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/metformin-la-thuoc-tri-benh-tieu-duong-vi",                 "title": "Metformin là thuốc trị bệnh tiểu đường",        "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/thuoc-metformin-luu-y-khi-dieu-tri-tieu-duong-type-2-vi",   "title": "Thuốc metformin lưu ý điều trị",                "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/phac-do-dieu-tri-tieu-duong-type-2-vi",                     "title": "Phác đồ điều trị tiểu đường type 2",            "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/thuoc-tieu-duong-co-nhung-nhom-thuoc-nao-dung-ra-sao",              "title": "Thuốc tiểu đường nhóm nào - Medlatec",           "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/tim-hieu-cu-the-ve-phac-do-dieu-tri-dai-thao-duong",                "title": "Phác đồ điều trị ĐTĐ - Medlatec",               "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/mot-so-loai-thuoc-tay-tri-tieu-duong-tot-nhat-hien-nay",            "title": "Thuốc tây trị tiểu đường tốt nhất",             "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/thuoc/metformin/",                                                        "title": "Thuốc Metformin - HelloBacsi",                    "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/thuoc-dieu-tri-dai-thao-duong/",               "title": "Thuốc điều trị ĐTĐ - HelloBacsi",               "language": "vi", "priority": 2},
        {"url": "https://www.medicalnewstoday.com/articles/323185",                                               "title": "Metformin overview",                              "language": "en", "priority": 3},
        {"url": "https://www.medicalnewstoday.com/articles/317483",                                               "title": "Insulin types",                                   "language": "en", "priority": 3},
        {"url": "https://www.mayoclinic.org/diseases-conditions/type-2-diabetes/in-depth/diabetes-treatment/art-20051004", "title": "Diabetes treatment - Mayo",             "language": "en", "priority": 2},
        # --- CDC Site Index bổ sung ---
        {"url": "https://www.cdc.gov/diabetes/about/how-to-use-insulin.html", "title": "Insulin: How to Use It - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/about/4-ways-to-take-insulin.html", "title": "4 Ways To Take Insulin - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/about/insulin-resistance-type-2-diabetes.html", "title": "Insulin Resistance and Type 2 Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/treatment/type-1-diabetes-early-treatment.html", "title": "Early Treatment for Type 1 Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/data-research/research/new-diabetes-medicines.html", "title": "Use of New Diabetes Medicines - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/articles/diabetes-and-your-medicines.html", "title": "Take Charge of Your Diabetes Medicines - CDC", "language": "en", "priority": 1},
        # --- diabetes.co.uk bổ sung ---
        {"url": "https://www.diabetes.co.uk/treatment-for-type1-diabetes.html", "title": "Treatment for type 1 diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/treatment-for-type2-diabetes.html", "title": "Treatment for type 2 diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/insulin-resistance.html", "title": "Insulin resistance - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/Diabetes-drugs.html", "title": "Diabetes medication A to Z - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-medication/diabetes-and-byetta.html", "title": "Byetta (Exenatide) - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-medication/forxiga-dapagliflozin.html", "title": "Forxiga (Dapagliflozin) - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/about-insulin.html", "title": "Insulin - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/insulin/adjusting-basal-bolus-insulin-doses.html", "title": "Adjusting basal and bolus insulin - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/insulin/how-to-inject-insulin.html", "title": "How to inject insulin - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/insulin/Insulin-pumps.html", "title": "Insulin pumps - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/insulin/Getting-an-insulin-pump.html", "title": "Getting an insulin pump - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/insulin/how-insulin-pumps-work.html", "title": "How insulin pumps work - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-medication/diabetes-and-januvia.html", "title": "Januvia (Sitagliptin) - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-medication/diabetes-and-metformin.html", "title": "Metformin: Uses, Dosages, Side Effects - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-medication/sulphonylureas.html", "title": "Sulphonylureas - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-medication/diabetes-and-victoza.html", "title": "Victoza - Diabetes.co.uk", "language": "en", "priority": 2},
    ],

    "complication/cardiovascular": [
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/heart-disease-stroke", "title": "Heart Disease - NIDDK",                 "language": "en", "priority": 1},
        {"url": "https://www.heart.org/en/health-topics/diabetes/diabetes-complications-and-risks",               "title": "Diabetes and Heart Disease - AHA",                "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/complications/stroke",                                "title": "Stroke and diabetes",                             "language": "en", "priority": 1},
        {"url": "https://www.vinmec.com/vie/bai-viet/bien-chung-tren-benh-nhan-dai-thao-duong-vi",               "title": "Biến chứng tim mạch ĐTĐ - Vinmec",              "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/tim-hieu-chi-tiet-ve-dai-thao-duong-gay-bien-chung-mach-mau-s195-n27219", "title": "ĐTĐ biến chứng mạch máu - Medlatec",     "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/bien-chung-tieu-duong/bien-chung-cap-tinh-cua-benh-tieu-duong/", "title": "Biến Chứng Tim Mạch - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://www.medicalnewstoday.com/articles/317718",                                               "title": "Diabetes and cardiovascular disease",             "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/health/type-2-diabetes/hypertension",                                 "title": "Hypertension and diabetes",                      "language": "en", "priority": 3},
        {"url": "https://www.mayoclinic.org/diseases-conditions/diabetes/in-depth/diabetes-and-heart-disease/art-20047034", "title": "Diabetes and heart disease - Mayo",    "language": "en", "priority": 2},
        # --- CDC Site Index bổ sung ---
        {"url": "https://www.cdc.gov/diabetes/diabetes-complications/diabetes-and-your-heart.html", "title": "Diabetes and Your Heart - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-complications/statins-and-diabetes.html", "title": "Statins and Diabetes: What You Should Know - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/communication-resources/diabetes-heart-disease-chronic-kidney.html", "title": "The Diabetes, Heart Disease, and CKD Triangle - CDC", "language": "en", "priority": 1},
        # --- diabetes.co.uk bổ sung ---
        {"url": "https://www.diabetes.co.uk/dyslipidemia.html", "title": "Dyslipidemia - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-complications/heart-disease.html", "title": "Heart disease - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-complications/high-blood-pressure.html", "title": "High blood pressure - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-complications/high-triglyceride-levels.html", "title": "High triglyceride levels - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-complications/diabetes-and-stroke.html", "title": "Stroke - Diabetes.co.uk", "language": "en", "priority": 2},
    ],

    "complication/nephropathy": [
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/diabetic-kidney-disease", "title": "Diabetic Kidney Disease - NIDDK",    "language": "en", "priority": 1},
        {"url": "https://www.kidney.org/diabetes",                                                                "title": "Diabetes and Kidney Disease - NKF",               "language": "en", "priority": 1},
        {"url": "https://www.vinmec.com/vie/bai-viet/tai-sao-dai-thao-duong-dan-toi-suy-vi",                    "title": "Tại sao ĐTĐ dẫn tới suy thận",                  "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tu-dien-benh-ly/bien-chung-cua-dai-thao-duong-nen-tam-soat-khi-nao-va-o-dau-solqy", "title": "Biến chứng ĐTĐ tầm soát thận",          "language": "vi", "priority": 2},
        {"url": "https://www.medicalnewstoday.com/articles/311204",                                               "title": "Diabetic nephropathy",                            "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/health/type-2-diabetes/nephropathy",                                  "title": "Diabetic Nephropathy - Healthline",               "language": "en", "priority": 3},
        {"url": "https://www.mayoclinic.org/diseases-conditions/diabetic-nephropathy/symptoms-causes/syc-20354556", "title": "Diabetic nephropathy - Mayo",                 "language": "en", "priority": 2},
        # --- CDC Site Index bổ sung ---
        {"url": "https://www.cdc.gov/diabetes/diabetes-complications/diabetes-and-chronic-kidney-disease.html", "title": "Chronic Kidney Disease - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/data-research/research/kidney-failure-diabetes.html", "title": "Kidney Failure and Diabetes - CDC", "language": "en", "priority": 1},
        # --- diabetes.co.uk bổ sung ---
        {"url": "https://www.diabetes.co.uk/diabetes-complications/kidney-disease.html", "title": "Diabetic nephropathy - Diabetes.co.uk", "language": "en", "priority": 2},
    ],

    "complication/neuropathy": [
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/nerve-damage-diabetic-neuropathies", "title": "Diabetic Neuropathy - NIDDK", "language": "en", "priority": 1},
        {"url": "https://www.vinmec.com/vie/bai-viet/benh-ly-kinh-dai-thao-duong-nhung-dieu-can-biet-vi",       "title": "Bệnh lý kinh ĐTĐ",                              "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/bien-chung-tieu-duong/bien-chung-te-bi-chan-tay-o-nguoi-dai-thao-duong/", "title": "Biến chứng tê bì chân tay - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://www.medicalnewstoday.com/articles/316427",                                               "title": "Diabetic neuropathy",                             "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/health/type-2-diabetes/diabetic-neuropathy",                          "title": "Diabetic neuropathy - Healthline",                "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/health/peripheral-neuropathy",                                        "title": "Peripheral neuropathy",                           "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/health/autonomic-neuropathy",                                         "title": "Autonomic neuropathy",                            "language": "en", "priority": 3},
        {"url": "https://www.mayoclinic.org/diseases-conditions/diabetic-neuropathy/symptoms-causes/syc-20371580", "title": "Diabetic neuropathy - Mayo",                  "language": "en", "priority": 2},
        # --- CDC Site Index bổ sung ---
        {"url": "https://www.cdc.gov/diabetes/diabetes-complications/diabetes-and-nerve-damage.html", "title": "Nerve Damage - CDC", "language": "en", "priority": 1},
        # --- diabetes.co.uk bổ sung ---
        {"url": "https://www.diabetes.co.uk/diabetes-complications/diabetes-neuropathy.html", "title": "Diabetic neuropathy - Diabetes.co.uk", "language": "en", "priority": 2},
    ],

    "complication/pregnancy": [
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/what-is-diabetes/gestational",   "title": "Gestational Diabetes - NIDDK",                    "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/risk-factors/gestational-diabetes.html",                            "title": "Gestational Diabetes - CDC",                      "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/gestational-diabetes/symptoms",                       "title": "Gestational diabetes symptoms",                   "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/gestational-diabetes/treatments",                     "title": "Gestational diabetes treatments",                 "language": "en", "priority": 1},
        {"url": "https://www.vinmec.com/vie/bai-viet/quan-ly-dai-thao-duong-thai-ky-nao-vi",                     "title": "Quản lý ĐTĐ thai kỳ",                           "language": "vi", "priority": 2},
        {"url": "https://www.vinmec.com/vie/bai-viet/dai-thao-duong-thai-ky-va-che-do-dinh-duong-cho-dai-thao-duong-thai-ky-vi", "title": "ĐTĐ thai kỳ và dinh dưỡng",     "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/tieu-duong-thai-ky-nen-an-gi-vao-bua-sang-bua-trua-va-toi-de-thai-ky-khoe-manh", "title": "Tiểu đường thai kỳ nên ăn gì",    "language": "vi", "priority": 2},
        {"url": "https://www.medicalnewstoday.com/articles/245310",                                               "title": "Gestational diabetes",                            "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/health/gestational-diabetes",                                         "title": "Gestational Diabetes - Healthline",               "language": "en", "priority": 3},
        {"url": "https://www.mayoclinic.org/diseases-conditions/gestational-diabetes/symptoms-causes/syc-20355339", "title": "Gestational diabetes - Mayo",                 "language": "en", "priority": 2},
        # --- CDC Site Index bổ sung ---
        {"url": "https://www.cdc.gov/diabetes/about/type-1-diabetes-pregnancy.html", "title": "Type 1 Diabetes and Pregnancy - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/about/gestational-diabetes.html", "title": "Gestational Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/about/gestational-diabetes-postpartum-depression.html", "title": "Gestational Diabetes and Postpartum Depression - CDC", "language": "en", "priority": 1},
        # --- diabetes.co.uk bổ sung ---
        {"url": "https://www.diabetes.co.uk/pregnancy-complications/fertility-and-diabetes.html", "title": "Fertility and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-pregnancy.html", "title": "Pregnancy and diabetes - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes_care/blood-sugar-levels-during-pregnancy.html", "title": "Blood glucose levels during pregnancy - Diabetes.co.uk", "language": "en", "priority": 2},
    ],

    "complication/retinopathy": [
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/diabetic-eye-disease", "title": "Diabetic Eye Disease - NIDDK",          "language": "en", "priority": 1},
        {"url": "https://www.nei.nih.gov/learn-about-eye-health/eye-conditions-and-diseases/diabetic-retinopathy", "title": "Diabetic Retinopathy - NEI",                 "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/complications/retinopathy",                           "title": "Retinopathy - Diabetes UK",                      "language": "en", "priority": 1},
        {"url": "https://www.medicalnewstoday.com/articles/323387",                                               "title": "Diabetic retinopathy",                            "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/health/type-2-diabetes/retinopathy",                                  "title": "Diabetic Retinopathy - Healthline",               "language": "en", "priority": 3},
        {"url": "https://www.mayoclinic.org/diseases-conditions/diabetic-retinopathy/symptoms-causes/syc-20371611", "title": "Diabetic retinopathy - Mayo",                 "language": "en", "priority": 2},
        # --- CDC Site Index bổ sung ---
        {"url": "https://www.cdc.gov/diabetes/diabetes-complications/diabetes-and-vision-loss.html", "title": "Vision Loss - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/data-research/research/eye-complications.html", "title": "Treatments for Diabetes Eye Complications - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/communication-resources/14-million-people-diabetic-retinopathy-2050.html", "title": "Diabetic Retinopathy by 2050 - CDC", "language": "en", "priority": 1},
        # --- diabetes.co.uk bổ sung ---
        {"url": "https://www.diabetes.co.uk/diabetes-complications/diabetes-and-blindness.html", "title": "Blindness - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-complications/diabetic-retinopathy.html", "title": "Diabetic retinopathy - Diabetes.co.uk", "language": "en", "priority": 2},
    ],

    "complication/foot_care": [
        {"url": "https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/foot-problems", "title": "Diabetic Foot Problems - NIDDK",             "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org/diabetes/complications/foot-complications",                             "title": "Foot Complications - ADA",                        "language": "en", "priority": 1},
        {"url": "https://www.diabetes.org.uk/about-diabetes/complications/feet",                                  "title": "Diabetic feet - Diabetes UK",                     "language": "en", "priority": 1},
        {"url": "https://www.vinmec.com/vie/bai-viet/benh-ly-ban-chan-o-nguoi-benh-dai-thao-duong-vi",           "title": "Bệnh lý bàn chân ở người bệnh ĐTĐ",             "language": "vi", "priority": 2},
        {"url": "https://medlatec.vn/tin-tuc/nhung-bien-chung-cua-benh-tieu-duong-ban-nen-biet-de-phong-ngua",   "title": "Biến chứng bàn chân ĐTĐ - Medlatec",            "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/bien-chung-tieu-duong/cham-soc-ban-chan-tieu-duong/", "title": "Chăm sóc bàn chân tiểu đường - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://hellobacsi.com/tieu-duong-dai-thao-duong/bien-chung-tieu-duong/bien-chung-te-bi-chan-tay-o-nguoi-dai-thao-duong/", "title": "Biến chứng tê bì bàn chân - HelloBacsi", "language": "vi", "priority": 2},
        {"url": "https://www.medicalnewstoday.com/articles/317465",                                               "title": "Diabetic foot care",                              "language": "en", "priority": 3},
        {"url": "https://www.healthline.com/health/charcot-foot",                                                 "title": "Charcot foot in diabetes",                       "language": "en", "priority": 3},
        {"url": "https://www.mayoclinic.org/diseases-conditions/diabetes/in-depth/amputation-and-diabetes/art-20048262", "title": "Amputation and diabetes - Mayo",         "language": "en", "priority": 2},
        # --- CDC Site Index bổ sung ---
        {"url": "https://www.cdc.gov/diabetes/diabetes-complications/diabetes-and-your-feet.html", "title": "Your Feet and Diabetes - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-complications/preventing-diabetes-related-amputations.html", "title": "Preventing Diabetes-Related Amputations - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-complications/diabetes-related-amputations-and-mental-health.html", "title": "Diabetes-Related Amputations and Mental Health - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/diabetes-complications/recovering-from-a-diabetes-related-amputation.html", "title": "Recovering from a Diabetes-Related Amputation - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/communication-resources/diabetes-foot-problems-when-to-see-your-doctor.html", "title": "Diabetes Foot Problems: When to See Your Doctor - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/communication-resources/tips-for-healthy-feet.html", "title": "Tips for Healthy Feet - CDC", "language": "en", "priority": 1},
        {"url": "https://www.cdc.gov/diabetes/communication-resources/diabetes-related-amputations.html", "title": "Diabetes-Related Amputations - CDC", "language": "en", "priority": 1},
        # --- diabetes.co.uk bổ sung ---
        {"url": "https://www.diabetes.co.uk/diabetes-footcare.html", "title": "Looking after your feet - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-and-amputation.html", "title": "Amputation - Diabetes.co.uk", "language": "en", "priority": 2},
        {"url": "https://www.diabetes.co.uk/diabetes-complications/diabetic-foot-ulcers.html", "title": "Foot ulcers - Diabetes.co.uk", "language": "en", "priority": 2},
    ],
}


# ══════════════════════════════════════════════════════════════
#  STATE MANAGEMENT
# ══════════════════════════════════════════════════════════════

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
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "").replace(".", "_")
    path = parsed.path.strip("/").replace("/", "_")[:60]
    cat_clean = category.replace("/", "_")
    name = f"{cat_clean}__{domain}__{path}"
    name = re.sub(r"[^a-zA-Z0-9_\-]", "", name)
    return name[:120]


def _is_blocked_domain(url: str) -> bool:
    domain = urlparse(url).netloc.lower()
    return any(blocked in domain for blocked in BLOCKED_DOMAINS)


def _needs_playwright(url: str) -> bool:
    domain = urlparse(url).netloc.lower().replace("www.", "")
    return any(pw in domain for pw in PLAYWRIGHT_DOMAINS)


# ══════════════════════════════════════════════════════════════
#  PLAYWRIGHT FETCHER
# ══════════════════════════════════════════════════════════════

def _fetch_with_playwright(url: str) -> Tuple[Optional[bytes], str]:
    """
    Headless Chromium qua Playwright.
    Xử lý được: mayoclinic.org, diabetes.org/.uk, who.int,
    healthline.com (CSR), medicalnewstoday.com (CSR).

    Cài đặt:
        pip install playwright
        playwright install chromium
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None, "playwright_not_installed"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ]
            )
            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                java_script_enabled=True,
                ignore_https_errors=True,
            )
            page = context.new_page()

            # Chặn resource không cần thiết để tăng tốc
            page.route("**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,otf}", lambda route: route.abort())
            page.route("**/analytics*", lambda route: route.abort())
            page.route("**/gtm*", lambda route: route.abort())
            page.route("**/ads*", lambda route: route.abort())

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                # Chờ thêm 2s để JS render
                page.wait_for_timeout(2000)
            except PlaywrightTimeout:
                # Timeout nhưng có thể đã load xong một phần — vẫn lấy content
                pass

            content = page.content()
            browser.close()

            if len(content) < 500:
                return None, f"playwright_response_too_short ({len(content)}B)"

            return content.encode("utf-8"), "text/html; charset=utf-8"

    except Exception as e:
        return None, f"playwright_error: {str(e)[:100]}"


# ══════════════════════════════════════════════════════════════
#  EXTRACTION PIPELINE
# ══════════════════════════════════════════════════════════════

def _strip_junk_tags(html: str) -> str:
    JUNK_TAGS = [
        'script', 'style', 'noscript', 'iframe',
        'nav', 'header', 'footer', 'aside',
        'form', 'figure', 'picture', 'svg', 'canvas',
        'button', 'select', 'option', 'template',
    ]
    if BS4_AVAILABLE:
        soup = BeautifulSoup(html, 'html.parser')
        for tag in JUNK_TAGS:
            for el in soup.find_all(tag):
                el.decompose()
        JUNK_CLASSES = [
            'breadcrumb', 'sidebar', 'widget', 'advertisement', 'ads',
            'related', 'social', 'share', 'comment', 'popup', 'modal',
            'cookie', 'newsletter', 'subscribe', 'banner', 'promo',
            'sticky', 'overlay', 'dropdown', 'menu', 'navigation',
            'pagination', 'tag-list', 'taglist', 'author-box', 'byline',
            'table-of-contents', 'toc',
            'box-question', 'box-promotion', 'box-doctor',
            'box-appointment', 'block-booking',
            'related-article', 'related-post', 'related-news',
            'box-related', 'consultant-form', 'cta-block',
            'question-list', 'qa-list', 'rating',
        ]
        JUNK_IDS = [
            'sidebar', 'comments', 'disqus', 'social-share',
            'related-posts', 'newsletter', 'cookie-banner',
            'advertisement', 'floating', 'popup',
            'consultant', 'booking', 'appointment',
        ]
        for val in JUNK_CLASSES:
            for el in soup.find_all(
                attrs={'class': lambda v, _v=val: v and _v in ' '.join(v).lower() if v else False}
            ):
                el.decompose()
        for val in JUNK_IDS:
            for el in soup.find_all(
                attrs={'id': lambda v, _v=val: v and _v in v.lower() if v else False}
            ):
                el.decompose()
        for el in soup.find_all(attrs={'role': ['navigation', 'banner', 'complementary', 'contentinfo']}):
            el.decompose()
        return str(soup)
    for tag in JUNK_TAGS:
        html = re.sub(rf'<{tag}(\s[^>]*)?>.*?</{tag}>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    return html


def _find_content_container(html: str) -> Tuple[str, str]:
    MIN_LEN = 200
    if BS4_AVAILABLE:
        soup = BeautifulSoup(html, 'html.parser')
        SELECTORS = [
            ('css', 'div.detail-content'),
            ('css', 'div.detail__content'),
            ('css', 'section.detail-content'),
            ('css', 'div#cDetail'),
            ('css', 'div.content-detail'),
            ('css', 'div.article-detail'),
            ('css', 'div.news-detail'),
            ('css', 'div.detail-news'),
            ('css', 'div[class*="detail-news"]'),
            ('css', 'div.singular-content'),
            ('css', 'div.hb-post-content'),
            ('css', 'div[class*="post-content"]'),
            ('css', 'div[class*="article__body"]'),
            ('css', 'div.entry-content'),
            ('css', 'div.post-content'),
            ('css', 'div.article__body'),
            ('css', 'div.article-body'),
            ('css', 'div[class*="article-content"]'),

            # ADA specific
            ('css', 'div.field-type-text-with-summary'),
            ('css', 'div.view-content'),
            ('tag', 'main'),
            ('tag', 'article'),
            ('attr', {'role': 'main'}),
            ('css', 'div#main-content'),
            ('css', 'div.main-content'),
            ('css', 'div#content'),
        ]
        for sel_type, selector in SELECTORS:
            try:
                if sel_type == 'tag':
                    el = soup.find(selector)
                elif sel_type == 'attr':
                    el = soup.find(attrs=selector)
                else:
                    el = soup.select_one(selector)
                if el:
                    text = el.get_text(separator='\n', strip=True)
                    if len(text) >= MIN_LEN:
                        return str(el), selector if isinstance(selector, str) else str(selector)
            except Exception:
                continue
        body = soup.find('body')
        return (str(body) if body else html), 'fallback'
    m = re.search(r'<main(\s[^>]*)?>(.+?)</main>', html, re.DOTALL | re.IGNORECASE)
    if m and len(m.group(2).strip()) > MIN_LEN:
        return m.group(2), '<main>'
    articles = re.findall(r'<article[^>]*>(.+?)</article>', html, re.DOTALL | re.IGNORECASE)
    if articles:
        best = max(articles, key=len)
        if len(best.strip()) > MIN_LEN:
            return best, '<article>'
    return html, 'fallback'


def _extract_nextjs_json(html: str) -> Optional[str]:
    json_str = None
    m = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>\s*(\{.+?\})\s*</script>',
        html, re.DOTALL
    )
    if m:
        json_str = m.group(1)
    if not json_str:
        m = re.search(r'window\.__NUXT__\s*=\s*(\{.+?\});', html, re.DOTALL)
        if m:
            json_str = m.group(1)
    if not json_str:
        return None
    try:
        data = json.loads(json_str)
    except Exception:
        return None
    collected: List[Tuple[int, str]] = []
    HIGH_PRIORITY = {
        'content', 'body', 'html', 'fullcontent', 'articlecontent',
        'maincontent', 'contenthtml', 'articlehtml', 'description',
        'noidung', 'noi_dung', 'baiviet', 'fulltext', 'text',
    }
    def harvest(obj, depth=0, parent_key=''):
        if depth > 15:
            return
        if isinstance(obj, str):
            if len(obj) > 200:
                if not obj.startswith(('http', 'data:', '/static', '/_next')):
                    if not re.match(r'^[a-zA-Z0-9+/=]{100,}$', obj):
                        if '<script' not in obj and 'function(' not in obj:
                            prio = 1 if parent_key.lower() in HIGH_PRIORITY else 5
                            collected.append((prio, obj))
        elif isinstance(obj, dict):
            for k, v in obj.items():
                harvest(v, depth + 1, k)
        elif isinstance(obj, list):
            for item in obj:
                harvest(item, depth + 1, parent_key)
    harvest(data)
    if not collected:
        return None
    collected.sort(key=lambda x: (x[0], -len(x[1])))
    merged_parts = []
    seen = set()
    for _, text in collected[:6]:
        key = text[:50]
        if key not in seen:
            seen.add(key)
            merged_parts.append(text)
        if len(merged_parts) >= 3:
            break
    merged = '\n\n'.join(merged_parts)
    if '<' in merged and '>' in merged:
        if BS4_AVAILABLE:
            merged = BeautifulSoup(merged, 'html.parser').get_text(separator='\n', strip=True)
        else:
            merged = re.sub(r'<[^>]+>', ' ', merged)
    merged = re.sub(r'\s{3,}', '\n\n', merged).strip()
    return merged if len(merged) > 200 else None


def _decode_html_entities(text: str) -> str:
    ENTITIES = {
        '&nbsp;': ' ', '&amp;': '&', '&lt;': '<', '&gt;': '>',
        '&quot;': '"', '&#39;': "'", '&apos;': "'",
        '&mdash;': '—', '&ndash;': '–',
        '&lsquo;': '\u2018', '&rsquo;': '\u2019',
        '&ldquo;': '\u201c', '&rdquo;': '\u201d',
        '&hellip;': '…', '&bull;': '•',
        '&lrm;': '', '&rlm;': '', '&#160;': ' ',
    }
    for ent, char in ENTITIES.items():
        text = text.replace(ent, char)
    text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
    return text


def _truncate_at_content_boundary(text: str) -> str:
    END_MARKERS = [
        r'để đặt lịch khám tại viện',
        r'quý khách vui lòng bấm số hotline',
        r'tải và đặt lịch khám tự động',
        r'có thể bạn quan tâm',
        r'để lại thông tin tư vấn',
        r'bài viết có hữu ích hay không',
        r'bài viết liên quan',
        r'liên hệ ngay với số hotline của medlatec',
        r'quý khách hàng vui lòng lựa chọn dịch vụ',
        r'medically reviewed by',
        r'^references?\s*$',
        r'^sources?\s*$',
        r'last (reviewed|updated|modified)',
        r'was this page helpful',
        r'sign up for our health tip',
    ]
    lines = text.split('\n')
    cut_index = len(lines)
    for i, line in enumerate(lines):
        normalized = line.strip().lower()
        if not normalized:
            continue
        for marker in END_MARKERS:
            if re.search(marker, normalized):
                if i > len(lines) * 0.2:
                    cut_index = i
                    break
        if cut_index < len(lines):
            break
    return '\n'.join(lines[:cut_index]).strip()


def _strip_accents(s: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )


def _remove_ui_noise(text: str) -> str:
    MEDICAL_PATTERN = re.compile(
        r'(\d+[\.,]\d+\s*(mg|mmol|g|iu|mcg|ml|%)|'
        r'insulin|glucose|hba1c|đường huyết|đái tháo|tiểu đường|'
        r'bệnh nhân|điều trị|chẩn đoán|triệu chứng|biến chứng|'
        r'blood sugar|diabetes|hypogly|hypergly|ketoacid)',
        re.IGNORECASE
    )
    NOISE_PATTERNS = [
        r'^(home|trang chu|about|ve chung toi|contact|lien he|sitemap)$',
        r'^(privacy policy|terms of use|disclaimer|accessibility)$',
        r'^(view all|see all|xem tat ca|read more|doc them|back to top|load more)$',
        r'^(facebook|linkedin|twitter|instagram|youtube|pinterest|tiktok|zalo|telegram)$',
        r'^(share|chia se|print|in bai|email this|subscribe|sign.?up|newsletter|copy link)$',
        r'^(accept all|reject all|cookie settings|quang cao|advertisement)$',
        r'^sources?$', r'^references?$', r'^citations?$',
        r'^medically reviewed by$', r'^written by$', r'^fact checked by$',
        r'^content source:$', r'^page last reviewed$',
        r'^©.*$', r'^all rights reserved$',
        r'^official (website|government)$',
        r'^secure \.gov website$',
        r'^here.?s how you know$',
        r'^dat lich( kham)?$',
        r'^tu van mien phi$',
        r'^(hotline|lien he|call us):?\s*[\d\s\-\.]+$',
        r'^xem them bai( viet)?$',
        r'^bai viet lien quan$',
        r'^tags?:\s*$',
        r'^\d{3,4}[.\s\-]\d{3,}',
        r'^[\s\-_|•·*#=]{3,}$',
    ]
    SHORT_LINE_PATTERNS = [
        r'^(for everyone|health care providers?|public health)$',
        r'^(basics|symptoms?|testing|risk factors?|treatment|prevention|living with)$',
        r'^(national center for|division of|cdc twenty|cdc 24/7)$',
    ]
    lines = text.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append('')
            continue
        if MEDICAL_PATTERN.search(stripped):
            result.append(stripped)
            continue
        normalized = _strip_accents(stripped.lower())
        is_noise = any(re.fullmatch(p, normalized) for p in NOISE_PATTERNS)
        if not is_noise and len(stripped) < 60:
            is_noise = any(re.fullmatch(p, normalized) for p in SHORT_LINE_PATTERNS)
        if not is_noise:
            result.append(stripped)
    cleaned = re.sub(r'\n{3,}', '\n\n', '\n'.join(result))
    return cleaned.strip()


def extract_article_text(html: str, title: str = '') -> Tuple[str, str]:
    clean_html = _strip_junk_tags(html)
    content_html, method = _find_content_container(clean_html)
    if BS4_AVAILABLE:
        soup = BeautifulSoup(content_html, 'html.parser')
        text = soup.get_text(separator='\n', strip=True)
    else:
        text = re.sub(r'<[^>]+>', ' ', content_html)
        text = _decode_html_entities(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    if method == 'fallback' or len(text.split()) < 150:
        json_text = _extract_nextjs_json(html)
        if json_text and len(json_text.split()) > len(text.split()) * 1.2:
            text = json_text
            method = '__NEXT_DATA__'
    text = _truncate_at_content_boundary(text)
    text = _remove_ui_noise(text)
    return text.strip(), method


# ══════════════════════════════════════════════════════════════
#  HTTP FETCHER (requests)
# ══════════════════════════════════════════════════════════════

def _fetch_with_requests(url: str, max_retries: int = 3) -> Tuple[Optional[bytes], str]:
    try:
        import requests
        from requests.packages.urllib3.exceptions import InsecureRequestWarning
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    except ImportError:
        return _fetch_with_urllib(url, max_retries)

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    session = requests.Session()

    for attempt in range(max_retries):
        try:
            ua = random.choice(USER_AGENTS)
            headers = {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "no-cache",
                "Referer": base_url,
                "DNT": "1",
            }
            resp = session.get(url, headers=headers, timeout=20, verify=False, allow_redirects=True)
            content_type = resp.headers.get("Content-Type", "")

            if len(resp.content) < 1000:
                return None, f"response_too_short ({len(resp.content)} bytes)"

            preview = resp.text[:3000].lower()
            captcha_signals = [
                'captcha', 'are you a robot', 'verify you are human',
                'access denied', 'cloudflare', 'ddos protection',
                'please enable javascript', 'checking your browser',
                'just a moment', 'ray id', 'cf-browser-verification',
            ]
            if any(sig in preview for sig in captcha_signals):
                return None, "blocked_by_captcha"

            return resp.content, content_type

        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(f"    Attempt {attempt+1} failed: {str(e)[:80]} — retry in {wait}s")
                time.sleep(wait)
            else:
                return None, str(e)

    return None, "max_retries_exceeded"


def _fetch_with_urllib(url: str, max_retries: int = 3) -> Tuple[Optional[bytes], str]:
    import urllib.request
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": base_url,
                "Connection": "keep-alive",
            })
            with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read()
            if len(raw) < 500:
                return None, f"response_too_short ({len(raw)} bytes)"
            return raw, content_type
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None, str(e)
    return None, "max_retries_exceeded"


# ══════════════════════════════════════════════════════════════
#  MAIN CRAWL FUNCTION  — smart fallback sang Playwright
# ══════════════════════════════════════════════════════════════

def crawl_url(
    url: str, title: str, category: str,
    language: str, priority: int, output_dir: Path
) -> Optional[Path]:

    # Bỏ qua domain bị block hoàn toàn
    if _is_blocked_domain(url):
        logger.warning(f"  ⛔ Skip domain bị block: {urlparse(url).netloc}")
        return None

    html = ""
    method_used = "requests"

    # Nếu domain cần Playwright → dùng Playwright ngay từ đầu
    if _needs_playwright(url):
        if PLAYWRIGHT_AVAILABLE:
            logger.debug(f"    → Playwright (domain trong PLAYWRIGHT_DOMAINS)")
            raw, content_type = _fetch_with_playwright(url)
            method_used = "playwright_direct"
        else:
            logger.warning(f"    ⚠ Playwright chưa cài, thử requests cho {urlparse(url).netloc}")
            raw, content_type = _fetch_with_requests(url)
    else:
        raw, content_type = _fetch_with_requests(url)

    # Nếu requests fail → fallback Playwright
    if raw is None:
        if PLAYWRIGHT_AVAILABLE:
            logger.info(f"    → Playwright fallback (requests fail: {content_type[:50]})")
            raw, content_type = _fetch_with_playwright(url)
            method_used = "playwright_fallback"
        else:
            logger.error(f"  ✗ Fetch thất bại [{title[:40]}]: {content_type}")
            return None

    if raw is None:
        logger.error(f"  ✗ Fetch thất bại cả requests + Playwright [{title[:40]}]")
        return None

    if "application/pdf" in content_type or url.lower().endswith(".pdf"):
        filename = _url_to_filename(url, category) + ".pdf"
        out_path = output_dir / filename
        out_path.write_bytes(raw)
        logger.success(f"  ✅ PDF: {filename} ({len(raw)//1024}KB)")
        return out_path

    for enc in ["utf-8", "utf-8-sig", "windows-1252", "latin-1"]:
        try:
            html = raw.decode(enc)
            break
        except Exception:
            continue

    if not html:
        logger.error(f"  ✗ Không decode được HTML: {url[:60]}")
        return None

    text, extract_method = extract_article_text(html, title)
    word_count = len(text.split())

    # Nếu word_count thấp và chưa dùng Playwright → thử Playwright
    if word_count < 80 and method_used == "requests" and PLAYWRIGHT_AVAILABLE:
        logger.info(f"    → Playwright fallback (word_count={word_count} < 80)")
        raw2, ct2 = _fetch_with_playwright(url)
        if raw2:
            html2 = raw2.decode("utf-8", errors="ignore")
            text2, extract_method2 = extract_article_text(html2, title)
            if len(text2.split()) > word_count:
                text, extract_method, word_count = text2, extract_method2, len(text2.split())
                method_used = "playwright_fallback"

    if word_count < 80:
        logger.warning(
            f"  ⚠ Bỏ qua [{title[:40]}] — "
            f"chỉ {word_count} từ (fetch={method_used}, extract={extract_method}). "
        )
        return None

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
        "fetch_method": method_used,
        "extraction_method": extract_method,
        "word_count": word_count,
        "verified_by_doctor": False,
    }

    content = (
        f"===METADATA===\n"
        f"{json.dumps(meta, ensure_ascii=False, indent=2)}\n"
        f"===CONTENT===\n"
        f"{title}\n\n"
        f"{text}"
    )

    filename_base = _url_to_filename(url, category)
    txt_path = output_dir / (filename_base + ".txt")
    txt_path.write_text(content, encoding="utf-8")
    logger.success(
        f"  ✅ [{method_used:22s}|{extract_method:18s}] "
        f"{filename_base[:45]}.txt ({word_count}w)"
    )
    return txt_path


# ══════════════════════════════════════════════════════════════
#  CDC AUTO-SPIDER
# ══════════════════════════════════════════════════════════════

def spider_cdc_diabetes(max_pages: int = 1000) -> List[Dict]:
    import urllib.request
    import ssl
    start_url = "https://www.cdc.gov/diabetes/index.html"
    visited: set = set()
    queue: List[str] = [start_url]
    sources: List[Dict] = []
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    logger.info(f"🕷 Spider CDC (max {max_pages} pages)...")
    while queue and len(sources) < max_pages:
        current_url = queue.pop(0)
        if current_url in visited:
            continue
        visited.add(current_url)
        try:
            req = urllib.request.Request(current_url, headers={"User-Agent": random.choice(USER_AGENTS)})
            with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else "CDC Diabetes Article"
            title = re.sub(r"\s*\|\s*(CDC|Diabetes).*$", "", title).strip()
            sources.append({"url": current_url, "title": title, "category": "cdc_auto_crawl", "language": "en", "priority": 1})
            if len(sources) % 10 == 0:
                logger.info(f"  ...{len(sources)} URLs found")
            links = re.findall(r'href=["\'](/diabetes/[^"\'#?]+)["\']', html)
            links += re.findall(r'href=["\'](https://www\.cdc\.gov/diabetes/[^"\'#?]+)["\']', html)
            for link in links:
                full_url = urljoin("https://www.cdc.gov", link) if link.startswith("/") else link
                if any(x in full_url.lower() for x in [".pdf", ".jpg", ".png", "espanol"]):
                    continue
                if full_url not in visited and full_url not in queue:
                    queue.append(full_url)
        except Exception as e:
            logger.debug(f"Skip {current_url}: {e}")
    logger.info(f"✅ Spider CDC done: {len(sources)} URLs")
    return sources


# ══════════════════════════════════════════════════════════════
#  ORCHESTRATION
# ══════════════════════════════════════════════════════════════

def crawl_category(
    category: str, sources: List[Dict],
    max_per_category: int = 100,
    skip_existing: bool = True,
    dry_run: bool = False,
) -> List[Path]:
    cat_dir = PDF_BASE_DIR / category
    cat_dir.mkdir(parents=True, exist_ok=True)
    state = _load_state()
    saved_files: List[Path] = []
    logger.info(f"\n📂 [{category}] {len(sources)} nguồn")
    count = 0
    for source in sources:
        if count >= max_per_category:
            logger.info(f"   Đạt giới hạn {max_per_category}")
            break
        url = source["url"]
        title = source.get("title", url)
        language = source.get("language", "vi")
        priority = source.get("priority", 3)
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        if skip_existing and url_hash in state:
            logger.info(f"  ⏭ Đã có: {title[:50]}")
            continue
        if dry_run:
            logger.info(f"  🔍 [DRY RUN] {url}")
            continue
        logger.info(f"  🌐 {title[:60]}")
        time.sleep(random.uniform(1.5, 3.0))  # Tăng delay khi có Playwright
        saved = crawl_url(url, title, category, language, priority, cat_dir)
        if saved:
            saved_files.append(saved)
            state[url_hash] = {
                "url": url, "title": title, "category": category,
                "saved_at": datetime.now().isoformat(), "file": str(saved.name),
            }
            _save_state(state)
            count += 1
    logger.info(f"   ✅ {count} file mới")
    return saved_files


def run_crawler(
    categories: Optional[List[str]] = None,
    max_per_category: int = 100,
    skip_existing: bool = True,
    dry_run: bool = False,
    ingest_after: bool = False,
    auto_cdc: bool = False,
):
    logger.info("=" * 60)
    logger.info("🕷  HEALTHCARE RAG — CRAWLER v4.2 (Anti-Block)")
    logger.info("=" * 60)

    if not BS4_AVAILABLE:
        logger.warning("⚠ BeautifulSoup chưa cài! pip install beautifulsoup4 lxml")
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning("⚠ Playwright chưa cài — một số site sẽ bị skip!")
        logger.warning("  Fix: pip install playwright && playwright install chromium")
    else:
        logger.info("✅ Playwright available — có thể crawl Mayo/ADA/WHO/Diabetes UK")

    sources_to_crawl = (
        {k: v for k, v in CRAWL_SOURCES.items() if k in categories}
        if categories else CRAWL_SOURCES.copy()
    )

    if auto_cdc:
        cdc_links = spider_cdc_diabetes(max_pages=max_per_category)
        if cdc_links:
            sources_to_crawl["cdc_auto_crawl"] = cdc_links

    logger.info(f"\n📋 {len(sources_to_crawl)} danh mục:")
    for cat in sources_to_crawl:
        logger.info(f"   - {cat} ({len(sources_to_crawl[cat])} nguồn)")

    all_saved: List[Path] = []
    for category, sources in sources_to_crawl.items():
        saved = crawl_category(
            category=category, sources=sources,
            max_per_category=max_per_category,
            skip_existing=skip_existing, dry_run=dry_run,
        )
        all_saved.extend(saved)

    logger.info("\n" + "=" * 60)
    logger.info(f"✅ XONG! Tổng file mới: {len(all_saved)}")
    if all_saved:
        logger.info("\n   Files đã lưu:")
        for f in all_saved[:10]:
            logger.info(f"     - {f.name}")
        if len(all_saved) > 10:
            logger.info(f"     ... và {len(all_saved)-10} file khác")

    if ingest_after and all_saved and not dry_run:
        logger.info("\n⚙ Ingest vào Qdrant...")
        try:
            from scripts.ingest import ingest
            ingest(PDF_BASE_DIR, incremental=True)
        except Exception as e:
            logger.error(f"Lỗi ingest: {e}. Chạy thủ công: python scripts/ingest.py --incremental")

    return all_saved


# ══════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Crawler tài liệu y tế — v4.2 Anti-Block",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Setup anti-block:
  pip install playwright beautifulsoup4 lxml
  playwright install chromium

Fix Docker DNS (niddk.nih.gov):
  Thêm vào docker-compose.yml, dưới service rag-api:
    dns:
      - 8.8.8.8
      - 1.1.1.1

Ví dụ:
  python scripts/crawler.py                    # Crawl tất cả
  python scripts/crawler.py -c diet medication # Chỉ 2 danh mục
  python scripts/crawler.py --force            # Force re-crawl
  python scripts/crawler.py --dry-run          # Preview URLs
        """
    )
    parser.add_argument("--category", "-c", nargs="+",
                        choices=list(CRAWL_SOURCES.keys()) + ["cdc_auto_crawl"])
    parser.add_argument("--max-per-category", "-m", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--auto-cdc", action="store_true")
    args = parser.parse_args()

    run_crawler(
        categories=args.category,
        max_per_category=args.max_per_category,
        skip_existing=not args.force,
        dry_run=args.dry_run,
        ingest_after=args.ingest,
        auto_cdc=args.auto_cdc,
    )