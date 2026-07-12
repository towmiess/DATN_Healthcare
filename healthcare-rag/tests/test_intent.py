"""tests/test_intent.py — Không cần Qdrant/Redis/GPU."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.retrieval.retriever import detect_intent, is_emergency


def test_emergency_vi():
    assert detect_intent("bị hạ đường huyết phải làm gì") == "emergency"
    assert detect_intent("đường huyết thấp cần xử lý ngay") == "emergency"


def test_emergency_flag():
    assert is_emergency("hạ đường huyết nguy hiểm") is True
    assert is_emergency("tiểu đường ăn phở được không") is False


def test_medication():
    assert detect_intent("uống metformin lúc nào tốt nhất") == "medication"
    assert detect_intent("liều insulin bao nhiêu") == "medication"


def test_diet():
    assert detect_intent("ăn phở được không") == "diet"
    assert detect_intent("chế độ ăn cho người tiểu đường") == "diet"


def test_blood_glucose():
    assert detect_intent("HbA1c bao nhiêu là ổn") == "blood_glucose"
    assert detect_intent("đường huyết sau ăn 180 mg/dL có cao không") == "blood_glucose"


def test_nephropathy():
    assert detect_intent("tiểu đường ảnh hưởng thận như thế nào") == "nephropathy"
    assert detect_intent("GFR giảm còn 45 có sao không") == "nephropathy"


def test_cardiovascular():
    assert detect_intent("tiểu đường tăng huyết áp điều trị thế nào") == "cardiovascular"
    assert detect_intent("cholesterol cao kèm tiểu đường") == "cardiovascular"


def test_pregnancy():
    assert detect_intent("mang thai bị tiểu đường thai kỳ") == "pregnancy"


def test_foot_care():
    assert detect_intent("bàn chân bị loét do tiểu đường") == "foot_care"


def test_general_fallback():
    assert detect_intent("tiểu đường là gì") == "general"
    assert detect_intent("hello world") == "general"


if __name__ == "__main__":
    test_emergency_vi()
    test_emergency_flag()
    test_medication()
    test_diet()
    test_blood_glucose()
    test_nephropathy()
    test_cardiovascular()
    test_pregnancy()
    test_foot_care()
    test_general_fallback()
    print("✅ Tất cả test intent passed!")
