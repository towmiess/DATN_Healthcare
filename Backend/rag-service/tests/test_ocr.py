"""tests/test_ocr.py — Không cần tesseract (chỉ test helper logic)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.ocr import is_garbled_vietnamese


def test_clean_english_not_garbled():
    text = "Diabetes mellitus is a chronic metabolic disease. Blood glucose levels are elevated."
    assert is_garbled_vietnamese(text) is False


def test_clean_vietnamese_not_garbled():
    text = "Đái tháo đường type 2 là bệnh mãn tính. Đường huyết cần được kiểm soát tốt."
    assert is_garbled_vietnamese(text) is False


def test_garbled_vni_font():
    # Mô phỏng text bị lỗi font VNI
    garbled = "TiIu IIIng type 2 laø beänh maïn tính. IIng huyeát caàn kieåm soaùt. " * 5
    assert is_garbled_vietnamese(garbled) is True


def test_short_text_not_garbled():
    # Văn bản quá ngắn → không kết luận garbled
    assert is_garbled_vietnamese("Hi") is False
    assert is_garbled_vietnamese("") is False


def test_signature_match():
    text = "ThIc haønh IIIng huyeát vaø mInh chaâu soáng khoûe. " * 4
    assert is_garbled_vietnamese(text) is True


if __name__ == "__main__":
    test_clean_english_not_garbled()
    test_clean_vietnamese_not_garbled()
    test_garbled_vni_font()
    test_short_text_not_garbled()
    test_signature_match()
    print("✅ Tất cả test OCR helper passed!")
