"""tests/test_loader.py — Không cần file PDF thực."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.loader import (
    detect_language,
    normalize_category,
    smart_category_from_name,
)


# ── Category detection ─────────────────────────────────────────

def test_category_from_folder_hint():
    assert smart_category_from_name("some_doc", "cardiovascular") == "cardiovascular"
    assert smart_category_from_name("some_doc", "nephropathy") == "nephropathy"
    assert smart_category_from_name("some_doc", "pregnancy") == "pregnancy"


def test_category_from_keyword():
    assert smart_category_from_name("kdigo_2022_ckd") == "nephropathy"
    assert smart_category_from_name("ada_11_chronic_kidney") == "nephropathy"
    assert smart_category_from_name("aha_heart_disease_2024") == "cardiovascular"
    assert smart_category_from_name("nice_ng3_pregnancy_diabetes") == "pregnancy"
    assert smart_category_from_name("insulin_therapy_guide") == "medication"
    assert smart_category_from_name("hypoglycemia_emergency") == "emergency"


def test_category_fallback_general():
    assert smart_category_from_name("unknown_file_xyz") == "general"


def test_normalize_category_alias():
    assert normalize_category("tim_mach") == "cardiovascular"
    assert normalize_category("than") == "nephropathy"
    assert normalize_category("che_do_an") == "diet"
    assert normalize_category("dieu_tri") == "medication"


def test_normalize_category_passthrough():
    assert normalize_category("cardiovascular") == "cardiovascular"
    assert normalize_category("diet") == "diet"


# ── Language detection ─────────────────────────────────────────

def test_detect_english_by_content():
    en_text = "Diabetes mellitus is a group of metabolic diseases. Blood glucose levels are high."
    assert detect_language(en_text) == "en"


def test_detect_vietnamese_by_content():
    vi_text = "Đái tháo đường type 2 là bệnh mãn tính phổ biến ở Việt Nam."
    assert detect_language(vi_text) == "vi"


def test_detect_by_filename_hint():
    assert detect_language("", filename="kdigo_2022_diabetes.pdf") == "en"
    assert detect_language("", filename="ada_standards_2026.pdf") == "en"
    assert detect_language("", filename="boyte_qd2388_vi.pdf") == "vi"


if __name__ == "__main__":
    test_category_from_folder_hint()
    test_category_from_keyword()
    test_category_fallback_general()
    test_normalize_category_alias()
    test_normalize_category_passthrough()
    test_detect_english_by_content()
    test_detect_vietnamese_by_content()
    test_detect_by_filename_hint()
    print("✅ Tất cả test loader passed!")
