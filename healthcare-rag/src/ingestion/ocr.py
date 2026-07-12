"""
src/ingestion/ocr.py
────────────────────
OCR fallback cho PDF scan/image.

Phụ thuộc hệ thống (cài 1 lần, không cần mỗi lần chạy):
  apt install tesseract-ocr tesseract-ocr-vie poppler-utils
  pip install pytesseract pdf2image

Nếu chưa cài → tự động bỏ qua (WARNING, không crash).
"""
from __future__ import annotations

import re
from pathlib import Path

from loguru import logger


# ── Kiểm tra dependency lúc import ─────────────────────────────
def _check_ocr_deps() -> bool:
    try:
        import pytesseract  # noqa: F401
        from pdf2image import convert_from_path  # noqa: F401
        return True
    except ImportError:
        return False

_OCR_AVAILABLE = _check_ocr_deps()

if not _OCR_AVAILABLE:
    logger.warning(
        "⚠ OCR không khả dụng — PDF scan sẽ bị bỏ qua.\n"
        "  Để bật OCR:\n"
        "    pip install pytesseract pdf2image\n"
        "  Và cài system package:\n"
        "    [Windows] https://github.com/UB-Mannheim/tesseract/wiki\n"
        "    [Linux]   apt install tesseract-ocr tesseract-ocr-vie poppler-utils"
    )


# ── Phát hiện font lỗi tiếng Việt ──────────────────────────────

def is_garbled_vietnamese(text: str) -> bool:
    """
    Phát hiện text bị lỗi font (VNI, TCVN3, reportlab không embed).
    Pattern điển hình: 'IIIng'='ường', 'ThIc'='Thực'.

    Returns True nếu văn bản nhiều khả năng bị mã hóa sai.
    """
    if not text or len(text) < 50:
        return False

    sample = text[:2_000]

    # Chữ ký đặc trưng font lỗi tiếng Việt
    garbled_signatures = [
        "IIIng", "ThIc", "TiIu", "bIu", "mInh",
        "sIng", "trIa", "IIng", "GIi",
        "nIi", "kIe", "vIt", "IIn ",
    ]
    if sum(sample.count(p) for p in garbled_signatures) >= 3:
        return True

    # Fallback: tỷ lệ pattern I kẹp giữa chữ thường–Hoa
    garbled = len(re.findall(r"[a-z]I[A-Z]|[A-Z]{2,}[a-z]{1,2}I", sample))
    words = len(sample.split()) or 1
    return (garbled / words) > 0.12


# ── OCR bằng Tesseract ──────────────────────────────────────────

def ocr_pdf(pdf_path: Path, dpi: int = 200, max_pages: int = 20) -> str:
    """
    Chuyển PDF → ảnh → OCR bằng Tesseract (vie+eng).

    Returns:
        Chuỗi text sau OCR, hoặc chuỗi rỗng nếu không khả dụng / thất bại.
    """
    if not _OCR_AVAILABLE:
        # Đã log khi import, không cần log lại mỗi file
        return ""

    try:
        import pytesseract
        from pdf2image import convert_from_path

        logger.info(f"  🔍 OCR: {pdf_path.name} (dpi={dpi}, max_pages={max_pages})")

        kwargs: dict = dict(dpi=dpi, first_page=1)
        if max_pages:
            kwargs["last_page"] = max_pages

        images = convert_from_path(str(pdf_path), **kwargs)
        if not images:
            logger.warning(f"  ⚠ convert_from_path trả về 0 ảnh: {pdf_path.name}")
            return ""

        page_texts: list[str] = []
        for idx, img in enumerate(images, 1):
            text = pytesseract.image_to_string(img, lang="vie+eng", config="--psm 3")
            cleaned = text.strip()
            if cleaned:
                page_texts.append(cleaned)
            logger.debug(f"    Trang {idx}/{len(images)}: {len(cleaned)} ký tự")

        result = "\n\n".join(page_texts)
        if result:
            logger.success(
                f"  ✅ OCR xong: {pdf_path.name} "
                f"({len(result)} ký tự, {len(images)} trang)"
            )
        else:
            logger.warning(
                f"  ⚠ OCR không có text: {pdf_path.name} "
                f"(chất lượng ảnh thấp hoặc PDF rỗng)"
            )
        return result

    except Exception as exc:
        logger.error(f"  ✗ OCR lỗi {pdf_path.name}: {exc}")
        return ""
