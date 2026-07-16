"""
tests/test_chunker.py
─────────────────────
Unit tests cho chunking logic — không cần Qdrant/Redis.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.chunking.chunker import chunk_documents


def _make_doc(content: str, category: str = "general") -> dict:
    return {
        "content": content, "source": "test", "category": category,
        "filename": "test.pdf", "document_id": "test_doc",
        "title": "Test", "source_url": "", "source_type": "document",
        "source_priority": 4, "verified_by_doctor": False,
        "published_date": "", "language": "vi",
    }


def test_basic_chunking():
    doc = _make_doc("Tiểu đường type 2 là bệnh mãn tính. " * 50)
    chunks = chunk_documents([doc])
    assert len(chunks) > 0
    for c in chunks:
        assert "text" in c
        assert "metadata" in c
        assert c["metadata"]["category"] == "general"


def test_short_doc_kept():
    """Tài liệu ngắn hơn chunk_size vẫn phải được giữ lại."""
    doc = _make_doc("Đường huyết bình thường lúc đói là 70-100 mg/dL. Sau ăn 2 giờ nên dưới 140 mg/dL. Cần theo dõi thường xuyên.")
    chunks = chunk_documents([doc])
    assert len(chunks) >= 1


def test_empty_doc_skipped():
    doc = _make_doc("")
    chunks = chunk_documents([doc])
    assert len(chunks) == 0


def test_metadata_fields():
    doc = _make_doc("Metformin là thuốc điều trị tiểu đường type 2. " * 10, "medication")
    chunks = chunk_documents([doc])
    assert chunks[0]["metadata"]["category"] == "medication"
    assert chunks[0]["metadata"]["document_id"] == "test_doc"
    assert "chunk_index" in chunks[0]["metadata"]
    assert "total_chunks" in chunks[0]["metadata"]


def test_long_doc_larger_chunks():
    """Tài liệu dài hơn 50k ký tự nên có chunk_size lớn hơn."""
    long_content = "Hướng dẫn điều trị tiểu đường theo ADA 2026. " * 1_500
    doc = _make_doc(long_content)
    chunks = chunk_documents([doc])
    # Tài liệu dài → ít chunks hơn so với chunk đều chunk_size nhỏ
    avg_len = sum(len(c["text"]) for c in chunks) / len(chunks)
    assert avg_len > 800, f"Avg chunk len quá nhỏ: {avg_len:.0f}"


if __name__ == "__main__":
    test_basic_chunking()
    test_short_doc_kept()
    test_empty_doc_skipped()
    test_metadata_fields()
    test_long_doc_larger_chunks()
    print("✅ Tất cả test chunker passed!")
