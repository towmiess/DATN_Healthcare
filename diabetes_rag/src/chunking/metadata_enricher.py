"""
Add structured metadata to every chunk.
This powers filtered retrieval (e.g. only nutrition topics, only Vietnamese).
"""
from typing import List
from langchain_core.documents import Document


# ── Topic detection keywords ─────────────────────────────────────────────────
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "blood_sugar": [
        "hba1c", "a1c", "glycemic", "glucose", "blood sugar", "hyperglycemia",
        "hypoglycemia", "insulin resistance", "postprandial", "fasting glucose",
        "đường huyết", "hba1c", "glucose máu",
    ],
    "nutrition": [
        "meal", "diet", "food", "nutrition", "carb", "carbohydrate", "calorie",
        "fiber", "protein", "fat", "glycemic index", "gi value", "portion",
        "breakfast", "lunch", "dinner", "snack", "bữa ăn", "thực phẩm",
        "dinh dưỡng", "chế độ ăn",
    ],
    "exercise": [
        "exercise", "physical activity", "walking", "sport", "workout",
        "sedentary", "steps", "aerobic", "resistance training",
        "vận động", "thể dục", "tập thể dục",
    ],
    "medication": [
        "insulin", "metformin", "medication", "drug", "dose", "injection",
        "sglt2", "glp-1", "sulfonylurea", "ozempic", "jardiance",
        "thuốc", "insulin", "tiêm",
    ],
    "complications": [
        "complication", "neuropathy", "retinopathy", "nephropathy",
        "cardiovascular", "kidney", "eye", "foot", "amputation",
        "biến chứng", "thận", "tim mạch",
    ],
    "lifestyle": [
        "sleep", "stress", "smoking", "alcohol", "weight loss",
        "obesity", "bmi", "lifestyle", "mental health",
        "giảm cân", "béo phì", "lối sống",
    ],
}

SOURCE_TRUST_LEVEL: dict[str, str] = {
    "ADA": "clinical_guideline",
    "WHO": "clinical_guideline",
    "NCBI": "research_paper",
    "PubMed": "research_paper",
    "USDA": "food_database",
    "GI Database": "food_database",
    "Viện Dinh Dưỡng": "food_database",
    "MOH": "clinical_guideline",
    "Endotext": "clinical_reference",
}


def detect_topic(text: str) -> str:
    text_lower = text.lower()
    scores = {
        topic: sum(1 for kw in keywords if kw in text_lower)
        for topic, keywords in TOPIC_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def detect_language(text: str) -> str:
    """Simple Vietnamese vs English detection."""
    vn_chars = set("àáâãèéêìíòóôõùúýăđơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỷỹ")
    vn_count = sum(1 for c in text.lower() if c in vn_chars)
    return "vi" if vn_count > len(text) * 0.03 else "en"


def get_trust_level(source: str) -> str:
    for key, level in SOURCE_TRUST_LEVEL.items():
        if key.lower() in source.lower():
            return level
    return "unknown"


def enrich(
    chunks: List[Document],
    source_name: str,
    doc_type: str,
    language: str = None,
) -> List[Document]:
    """
    Add structured metadata to each chunk:
    - topic: blood_sugar | nutrition | exercise | medication | complications | lifestyle | general
    - language: en | vi (auto-detected if not provided)
    - source: where this came from
    - doc_type: guideline | research_paper | food_database | qa
    - trust_level: clinical_guideline | research_paper | food_database
    - chunk_index: position within the source
    """
    for i, chunk in enumerate(chunks):
        detected_lang = language or detect_language(chunk.page_content)
        chunk.metadata.update({
            "source":       source_name,
            "doc_type":     doc_type,
            "language":     detected_lang,
            "topic":        detect_topic(chunk.page_content),
            "trust_level":  get_trust_level(source_name),
            "chunk_index":  i,
            "char_count":   len(chunk.page_content),
        })
    return chunks


# ── Usage ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample = [Document(page_content="Low-GI foods such as brown rice and oats help control blood glucose levels.")]
    enriched = enrich(sample, source_name="ADA 2026", doc_type="guideline")
    print(enriched[0].metadata)
    # → {'source': 'ADA 2026', 'topic': 'nutrition', 'language': 'en', ...}
