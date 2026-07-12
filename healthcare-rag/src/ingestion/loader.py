"""
src/ingestion/loader.py
───────────────────────
Load tài liệu từ data/pdfs/ và data/raw/.

Luồng:
  PDF  →  PyMuPDF (text layer)
       →  garbled check → OCR fallback (ocr.py)
  TXT  →  đọc trực tiếp (dành cho file crawled có metadata header)

Metadata được trích xuất từ:
  1. Tên file  (e.g. "cardiovascular__aha_2024.pdf" → category + source)
  2. data/raw/{stem}.txt  (JSON metadata từ crawler)
  3. Smart keyword detection (KEYWORD_TO_CATEGORY)
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF
from loguru import logger
from tqdm import tqdm

from src.ingestion.ocr import is_garbled_vietnamese, ocr_pdf
from src.utils.config import cfg
from src.utils.text_normalize import normalize_spelling

# ── Thư mục ────────────────────────────────────────────────────
PDF_DIR = cfg.paths.pdf_dir
RAW_DIR = cfg.paths.raw_dir


# ================================================================
# CATEGORY MAPPING
# ================================================================

CATEGORY_ALIASES: Dict[str, str] = {
    "che_do_an":          "diet",
    "dieu_tri":           "medication",
    "chi_so_duong_huyet": "blood_glucose",
    "tieu_duong_type2":   "general",
    "the_duc_loi_song":   "lifestyle",
    "bien_chung":         "complication",
    "tim_mach":           "cardiovascular",
    "than":               "nephropathy",
    "mat_bien_chung":     "retinopathy",
    "than_kinh":          "neuropathy",
    "ban_chan":            "foot_care",
    "complication":       "complication",
    "cardiovascular":     "cardiovascular",
    "nephropathy":        "nephropathy",
    "retinopathy":        "retinopathy",
    "neuropathy":         "neuropathy",
    "foot_care":          "foot_care",
}

KEYWORD_TO_CATEGORY: Dict[str, str] = {
    # ADA chapters
    "ada_1.": "general",      "ada_2.": "diagnosis",
    "ada_3.": "lifestyle",    "ada_4.": "diagnosis",
    "ada_5.": "lifestyle",    "ada_6.": "blood_glucose",
    "ada_7.": "blood_glucose","ada_8.": "lifestyle",
    "ada_9.": "medication",   "ada_10.": "cardiovascular",
    "ada_11.": "nephropathy", "ada_12.": "retinopathy",
    "ada_13.": "general",     "ada_14.": "general",
    "ada_15.": "pregnancy",   "ada_16.": "general",
    "ada_17.": "general",
    "ada_introduction": "general", "ada_summary": "general",
    # Biến chứng
    "cardiovascular": "cardiovascular", "cardiac": "cardiovascular",
    "heart": "cardiovascular",          "stroke": "cardiovascular",
    "cvd": "cardiovascular",
    "retinopathy": "retinopathy",       "eye_disease": "retinopathy",
    "neuropathy": "neuropathy",         "nerve_damage": "neuropathy",
    "foot_care": "foot_care",           "foot_problem": "foot_care",
    "ban_chan": "foot_care",
    "nephropathy": "nephropathy",       "kidney": "nephropathy",
    "renal": "nephropathy",             "ckd": "nephropathy",
    "kdigo": "nephropathy",
    # Thai kỳ
    "pregnancy": "pregnancy", "thai_ky": "pregnancy",
    "prenatal": "pregnancy",  "postnatal": "pregnancy",
    "gestation": "pregnancy",
    # Thuốc
    "pharmacolog": "medication", "medication": "medication",
    "insulin": "medication",     "metformin": "medication",
    "ng28": "medication",        "nice_type2": "medication",
    "drug_therapy": "medication","dieu_tri": "medication",
    # Đường huyết
    "glycemic": "blood_glucose",        "blood_glucose": "blood_glucose",
    "blood_sugar": "blood_glucose",     "duong_huyet": "blood_glucose",
    "hba1c": "blood_glucose",           "glucose_monitor": "blood_glucose",
    # Cấp cứu
    "hypoglycemi": "emergency",         "low_blood_sugar": "emergency",
    "low_blood_glucose": "emergency",   "ha_duong": "emergency",
    "emergency": "emergency",           "disaster": "emergency",
    # Chẩn đoán
    "diagnosis": "diagnosis",           "chan_doan": "diagnosis",
    "classification": "diagnosis",      "screening": "diagnosis",
    # Chế độ ăn
    "diet": "diet",            "che_do_an": "diet",
    "nutrition": "diet",       "eating_plan": "diet",
    "dinh_duong": "diet",      "healthy_eating": "diet",
    # Lối sống
    "lifestyle": "lifestyle",            "exercise": "lifestyle",
    "the_duc": "lifestyle",              "loi_song": "lifestyle",
    "obesity": "lifestyle",              "weight_management": "lifestyle",
    "physical_activity": "lifestyle",
    # Tâm lý / tổng quát
    "mental_health": "general",          "mental": "general",
}

_EXPLICIT_FOLDERS = {
    "cardiovascular", "nephropathy", "neuropathy",
    "retinopathy",    "foot_care",   "pregnancy",
    "blood_glucose",  "diagnosis",   "diet",
    "medication",     "emergency",   "lifestyle", "general",
}


def normalize_category(category: str) -> str:
    return CATEGORY_ALIASES.get((category or "unknown").strip(), category or "unknown")


def smart_category_from_name(stem: str, folder_hint: str = "") -> str:
    """Detect category từ tên file + subfolder hint."""
    if folder_hint in _EXPLICIT_FOLDERS:
        return folder_hint

    s = stem.lower().replace("-", "_").replace(" ", "_")
    for kw in sorted(KEYWORD_TO_CATEGORY, key=len, reverse=True):
        if kw.lower().replace("-", "_") in s:
            return KEYWORD_TO_CATEGORY[kw]

    if folder_hint and folder_hint not in ("diabetes", "unknown", ""):
        return folder_hint

    return "general"


# ================================================================
# LANGUAGE DETECTION
# ================================================================

def detect_language(text: str, filename: str = "") -> str:
    fname = filename.lower()
    if any(x in fname for x in ["_en_", "_en.", "-en-", "-en.", "english", "_eng"]):
        return "en"
    if any(x in fname for x in ["_vi_", "_vi.", "-vi-", "-vi.", "viet", "vn_", "_vn."]):
        return "vi"

    en_hints = ["kdigo", "ada_", "dc24", "dc26", "nice", "who_",
                "niddk", "ncbi", "pubmed", "springer", "nature",
                "lancet", "nejm", "jama", "bmj", "idf"]
    if any(h in fname for h in en_hints):
        return "en"

    sample = text[:500]
    viet_chars = set("àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ")
    if sum(1 for c in sample.lower() if c in viet_chars) > 5:
        return "vi"

    en_kws = ["diabetes", "glucose", "insulin", "patient", "treatment", "management",
               "blood", "clinical", "therapy", "the ", "and ", "of ", "for ", "with "]
    if sum(1 for kw in en_kws if kw in sample.lower()) >= 3:
        return "en"

    return "vi"


# ================================================================
# RAW METADATA (từ crawler TXT header)
# ================================================================

def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_raw_metadata(stem: str, source_path: Optional[Path] = None) -> Dict:
    candidates: list[Path] = []
    if source_path is not None and source_path.exists():
        candidates.append(source_path)
    raw_path = RAW_DIR / f"{stem}.txt"
    if raw_path not in candidates and raw_path.exists():
        candidates.append(raw_path)

    for candidate in candidates:
        try:
            text = candidate.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "===METADATA===" not in text or "===CONTENT===" not in text:
            continue
        meta_part = text.split("===CONTENT===", 1)[0].replace("===METADATA===", "").strip()
        try:
            return json.loads(meta_part)
        except json.JSONDecodeError:
            continue
    return {}


# ================================================================
# PDF TEXT EXTRACTION
# ================================================================

def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text từ PDF.
      1. PyMuPDF (fast, text-based PDF)
      2. Garbled check → OCR fallback (scan PDF / bad font)
    """
    pymupdf_text = ""
    try:
        doc = fitz.open(str(pdf_path))
        pages: list[str] = []
        for page in doc:
            try:
                blocks = page.get_text("dict")["blocks"]
                page_text = ""
                for block in blocks:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            page_text += span.get("text", "")
                        page_text += "\n"
                    page_text += "\n"
            except Exception:
                page_text = page.get_text("text")
            if page_text.strip():
                pages.append(page_text)
        doc.close()
        pymupdf_text = "\n\n".join(pages)
    except Exception as exc:
        logger.debug(f"PyMuPDF lỗi {pdf_path.name}: {exc}")

    if pymupdf_text.strip():
        if not is_garbled_vietnamese(pymupdf_text):
            return pymupdf_text
        logger.info(f"  🔧 Font lỗi phát hiện: {pdf_path.name} → thử OCR")

    return ocr_pdf(pdf_path)


# ================================================================
# LOAD ALL PDFs / TXTs
# ================================================================

def _build_doc_record(text: str, pdf_path: Path, pdf_dir: Path) -> Dict:
    """Tạo dict tài liệu từ text + đường dẫn."""
    # Chuẩn hóa chính tả ("kì"→"kỳ", "týp/type"→"tuýp") trước khi chunk,
    # để dữ liệu lưu trong Qdrant đã nhất quán, không phụ thuộc LLM lúc trả lời.
    text = normalize_spelling(text)

    stem = pdf_path.stem

    # Folder hint
    try:
        rel = pdf_path.relative_to(pdf_dir)
        if len(rel.parts) >= 3:
            folder_hint = rel.parts[-2]
        elif len(rel.parts) >= 2:
            folder_hint = rel.parts[0]
        else:
            folder_hint = ""
    except ValueError:
        folder_hint = ""

    source = stem.split("__", 1)[1] if "__" in stem else stem
    raw_meta = parse_raw_metadata(stem, pdf_path)

    if raw_meta.get("category"):
        category = normalize_category(raw_meta["category"])
    else:
        category = smart_category_from_name(stem, folder_hint)

    return {
        "content":          text,
        "source":           raw_meta.get("source_name", source),
        "category":         category,
        "filename":         pdf_path.name,
        "document_id":      stem,
        "title":            raw_meta.get("document_title") or stem,
        "source_url":       raw_meta.get("url", ""),
        "source_type":      raw_meta.get("source_type", "document"),
        "source_priority":  _safe_int(raw_meta.get("source_priority"), 4),
        "verified_by_doctor": bool(raw_meta.get("verified_by_doctor", False)),
        "published_date":   raw_meta.get("published_date", ""),
        "language":         raw_meta.get("language") or detect_language(text, pdf_path.name),
    }


def load_all_documents(pdf_dir: Path) -> List[Dict]:
    """
    Đọc tất cả PDF + TXT trong thư mục và subfolder.

    Returns:
        List[Dict] — mỗi dict là một tài liệu với content + metadata.
    """
    pdf_files = sorted(pdf_dir.rglob("*.pdf"))
    txt_files = sorted(pdf_dir.rglob("*.txt"))

    total = len(pdf_files) + len(txt_files)
    logger.info(f"📂 Tìm thấy {len(pdf_files)} PDF + {len(txt_files)} TXT = {total} file")

    if total == 0:
        logger.warning(f"⚠ Không có tài liệu nào trong {pdf_dir}")
        return []

    documents: list[Dict] = []
    skipped_empty = 0
    short_kept = 0

    # ── PDF ────────────────────────────────────────────────────
    for pdf_path in tqdm(pdf_files, desc="Đọc PDF"):
        try:
            text = extract_text_from_pdf(pdf_path)
            if not text or not text.strip():
                logger.warning(f"  ⚠ Bỏ qua {pdf_path.name} — rỗng / OCR thất bại")
                skipped_empty += 1
                continue
            if len(text) < 100:
                logger.info(f"  📄 Tài liệu ngắn: {pdf_path.name} ({len(text)} ký tự) — vẫn index")
                short_kept += 1
            documents.append(_build_doc_record(text, pdf_path, pdf_dir))
        except Exception as exc:
            logger.error(f"  ✗ Lỗi đọc {pdf_path.name}: {exc}")

    # ── TXT (crawler output) ───────────────────────────────────
    for txt_path in tqdm(txt_files, desc="Đọc TXT"):
        try:
            raw = txt_path.read_text(encoding="utf-8", errors="ignore")
            # Bỏ phần METADATA header nếu có
            if "===CONTENT===" in raw:
                text = raw.split("===CONTENT===", 1)[1].strip()
            else:
                text = raw.strip()

            if not text:
                skipped_empty += 1
                continue

            # Reuse _build_doc_record — path xem như pseudo-PDF
            doc = _build_doc_record(text, txt_path, pdf_dir)
            doc["filename"] = txt_path.name
            doc["source_type"] = doc.get("source_type") or "web_article"
            documents.append(doc)
        except Exception as exc:
            logger.error(f"  ✗ Lỗi đọc {txt_path.name}: {exc}")

    logger.success(
        f"✅ Đọc xong {len(documents)} tài liệu "
        f"(bỏ qua {skipped_empty} rỗng, {short_kept} tài liệu ngắn được giữ lại)"
    )
    return documents
