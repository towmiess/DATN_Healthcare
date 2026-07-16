"""
src/retrieval/retriever.py
───────────────────────────
Intent detection + semantic retrieval + reranking.
"""
from __future__ import annotations

import unicodedata
from typing import Dict, List, Optional

from loguru import logger
from qdrant_client.models import FieldCondition, Filter, MatchAny

from src.utils.config import cfg
from src.vectordb.vector_store import VectorStore

_TOP_K         = cfg.retrieval.top_k
_CANDIDATE_MUL = cfg.retrieval.candidate_multiplier
_SIM_GENERAL   = cfg.retrieval.min_similarity_general
_SIM_SPECIFIC  = cfg.retrieval.min_similarity_specific
_W_SEMANTIC    = cfg.retrieval.rerank_semantic_weight
_W_PRIORITY    = cfg.retrieval.rerank_priority_weight

INTENT_CATEGORY_FILTERS: Dict[str, List[str]] = {
    "emergency":      ["emergency", "blood_glucose"],
    "medication":     ["medication", "blood_glucose"],
    "lifestyle":      ["lifestyle", "diet", "general"],
    "diet":           ["diet", "lifestyle"],
    "blood_glucose":  ["blood_glucose", "emergency"],
    "complication":   ["complication", "cardiovascular", "nephropathy",
                       "retinopathy", "neuropathy", "foot_care", "diagnosis", "general"],
    "cardiovascular": ["cardiovascular", "complication", "general"],
    "nephropathy":    ["nephropathy", "complication", "general"],
    "retinopathy":    ["retinopathy", "complication", "general"],
    "neuropathy":     ["neuropathy", "foot_care", "complication", "general"],
    "foot_care":      ["foot_care", "neuropathy", "complication", "general"],
    "diagnosis":      ["diagnosis", "general"],
    "pregnancy":      ["pregnancy", "general"],
    "general":        ["general", "diagnosis", "lifestyle"],
}

_SPECIFIC_INTENTS = {
    "emergency", "medication", "cardiovascular", "nephropathy",
    "retinopathy", "neuropathy", "foot_care", "pregnancy",
}

# Keyword dùng bản không dấu (sau khi _norm)
_INTENT_KEYWORDS: Dict[str, List[str]] = {
    "emergency":      ["ha duong huyet", "duong huyet thap", "ngat", "hon me",
                       "run tay", "mo hoi lanh", "cap cuu", "duoi 70"],
    "medication":     ["thuoc", "metformin", "insulin", "gliclazide", "lieu",
                       "uong thuoc", "tac dung phu", "don thuoc"],
    "lifestyle":     ["tap the duc", "the duc", "van dong", "di bo",
                       "chay bo", "exercise", "workout", "gym", "cardio", "yoga"],
    "blood_glucose":  ["duong huyet", "hba1c", "glucose", "mg/dl", "mmol",
                       "do duong", "chi so duong"],
    "diet":           ["thuc pham", "pho ", "bun ", "com trang",
                       "carb", "tinh bot", "che do an", "dinh duong",
                       "an gi ", "uong gi ", "nen an", "khong nen an"],
    "cardiovascular": ["tim mach", "dot quy", "nhoi mau", "tang huyet ap",
                       "huyet ap", "cholesterol", "suy tim", "stroke"],
    "nephropathy":    ["suy than", "benh than", "anh huong than", "bien chung than", "loc mau", "creatinine",
                       "microalbumin", "gfr", "kidney", "ckd"],
    "retinopathy":    ["vong mac", "mo mat", "thi luc", "kham mat",
                       "retinopathy", "mat bi mo"],
    "neuropathy":     ["te bi", "kho chan", "mat cam giac", "dau than kinh",
                       "neuropathy", "numbness"],
    "foot_care":      ["ban chan", "loet chan", "vet loet", "mong chan",
                       "foot ulcer", "diabetic foot"],
    "complication":   ["bien chung", "complication"],
    "pregnancy":      ["mang thai", "thai ky", "sau sinh", "tien san giat",
                       "gestational", "thai phu"],
    "diagnosis":      ["chan doan", "phan loai", "type 1", "type 2",
                       "tien tieu duong", "xet nghiem"],
}

_EMERGENCY_TRIGGERS = [
    "ha duong huyet", "duong huyet thap", "ngat xiu", "hon me",
    "co giat", "cap cuu", "duoi 70",
]

_EMERGENCY_INFO_SIGNALS = [
    "dau hieu", "trieu chung", "bieu hieu", "nhan biet",
    "la gi", "nhu the nao", "nhu nao", "khi nao",
    "huong dan", "cach", "phuong phap", "nguyen nhan",
    "tim hieu", "cho biet", "giai thich", "de biet",
]

def _norm(text: str) -> str:
    """
    Lowercase + bỏ dấu tiếng Việt đầy đủ:
      1. NFD decompose
      2. Bỏ combining marks (Mn)
      3. Thay đ/Đ → d/D (không handle được bởi NFD)
    """
    # Thay đ trước khi NFD vì đ không decompose
    text = text.replace("đ", "d").replace("Đ", "D")
    lowered = text.lower()
    no_accent = "".join(
        c for c in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(c) != "Mn"
    )
    return f" {no_accent} "


_COMPARISON_TRIGGERS = [
    "phan biet", "khac nhau", "so sanh", "giong nhau",
    "khac biet", "vs", "hay la", "hoac la",
]


def detect_intent(query: str) -> str:
    """
    Phân loại intent từ câu hỏi.
    Trả về: emergency | medication | diet | blood_glucose |
             cardiovascular | nephropathy | retinopathy |
             neuropathy | foot_care | complication | pregnancy | diagnosis | general
    """
    q = _norm(query)
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return intent
    return "general"


def detect_intents(query: str) -> List[str]:
    """
    Phát hiện TẤT CẢ intent khớp với câu hỏi (không chỉ 1).
    Dùng khi câu hỏi có tính so sánh/liệt kê nhiều khía cạnh
    (ví dụ: "phân biệt tiểu đường type 1, type 2 và thai kỳ").

    Trả về list intent theo thứ tự khớp, tối thiểu ["general"].
    """
    q = _norm(query)
    matched = [intent for intent, kws in _INTENT_KEYWORDS.items()
               if any(kw in q for kw in kws)]
    return matched or ["general"]

# Cac khai niem thuong duoc nhac trong cau hoi so sanh ve tieu duong.
_COMPARISON_SUBJECTS = [
    ("tien tieu duong",      ["tien tieu duong", "tien dai thao duong", "prediabetes"]),
    ("tieu duong thai ky",   ["thai ky", "mang thai", "gestational"]),
    ("tieu duong type 1",    ["type 1", "tuyp 1", "typ 1", "loai 1"]),
    ("tieu duong type 2",    ["type 2", "tuyp 2", "typ 2", "loai 2"]),
]


def extract_comparison_subjects(query: str) -> List[str]:
    """Tach cac khai niem cu the duoc nhac trong cau hoi so sanh."""
    q = _norm(query)
    found = []
    for label, kws in _COMPARISON_SUBJECTS:
        if any(kw in q for kw in kws):
            found.append(label)
    return found



def is_comparison_query(query: str) -> bool:
    """True nếu câu hỏi yêu cầu so sánh/phân biệt nhiều khái niệm."""
    q = _norm(query)
    return any(kw in q for kw in _COMPARISON_TRIGGERS)


def is_emergency(query: str) -> bool:
    """True nếu câu hỏi là tình huống khẩn cấp hạ đường huyết."""
    q = _norm(query)
    if not any(kw in q for kw in _EMERGENCY_TRIGGERS):
        return False
    if any(sig in q for sig in _EMERGENCY_INFO_SIGNALS):
        return False
    return True

class Retriever:
    """
    Semantic retrieval + reranking.

    Dùng:
        retriever = Retriever(vector_store)
        chunks = retriever.retrieve("Tiểu đường ăn phở được không?", top_k=4)
    """

    def __init__(self, vector_store: Optional[VectorStore] = None):
        self._store = vector_store or VectorStore()

    def retrieve(self, query: str, top_k: int = _TOP_K) -> List[Dict]:
        """
        Retrieve + rerank chunks phù hợp nhất.

        Luồng:
          1. Detect intent(s) → category list
             - Câu so sánh/phân biệt nhiều khái niệm → gộp category
               của TẤT CẢ intent khớp (tránh chỉ lấy 1 phía, ví dụ
               "phân biệt type 1, type 2 và thai kỳ" phải lấy cả
               diagnosis + pregnancy, không chỉ pregnancy)
          2. Search Qdrant với category filter (candidate_k = top_k × multiplier)
          3. Lọc theo min_similarity
          4. Rerank: 85% semantic score + 15% source priority
          5. Trả về top_k chunks tốt nhất
        """
        if is_comparison_query(query):
            subjects = extract_comparison_subjects(query)
            if len(subjects) >= 2:
                per_subject_k = max(3, top_k // len(subjects))
                all_chunks: List[Dict] = []
                seen_sources_global = set()
                # Category cho phep cho moi subject - loai bo nhieu tu cac
                # tai lieu dai da chu de (vd noi tiet chuyen hoa noi chung)
                _SUBJECT_ALLOWED_CATEGORIES = {
                    "tien tieu duong":    ["diagnosis", "general", "blood_glucose"],
                    "tieu duong thai ky": ["pregnancy"],
                    "tieu duong type 1":  ["diagnosis", "general", "medication"],
                    "tieu duong type 2":  ["diagnosis", "general", "medication"],
                }
                for subj in subjects:
                    try:
                        allowed_cats = _SUBJECT_ALLOWED_CATEGORIES.get(subj, [])
                        if allowed_cats:
                            subj_filter = Filter(must=[FieldCondition(
                                key="category", match=MatchAny(any=allowed_cats)
                            )])
                            sub_chunks = self._store.search(
                                f"{subj} là gì, đặc điểm, nguyên nhân, điều trị",
                                top_k=per_subject_k * _CANDIDATE_MUL,
                                qdrant_filter=subj_filter,
                            )
                        else:
                            sub_chunks = self._store.search(
                                f"{subj} là gì, đặc điểm, nguyên nhân, điều trị",
                                top_k=per_subject_k * _CANDIDATE_MUL,
                            )
                    except Exception as exc:
                        logger.warning(f"Search subject '{subj}' loi ({exc})")
                        sub_chunks = []
                    # Loc trung nguon (ca trong subject nay va voi cac subject truoc)
                    picked = []
                    for c in sub_chunks:
                        src = c["metadata"].get("source", "")
                        if src not in seen_sources_global:
                            seen_sources_global.add(src)
                            picked.append(c)
                        if len(picked) >= per_subject_k:
                            break
                    all_chunks.extend(picked)
                logger.debug(
                    f"  query='{query[:50]}' | per-subject retrieval | "
                    f"subjects={subjects} | total_unique={len(all_chunks)}"
                )
                return all_chunks[: max(top_k, len(subjects) * 3)]

            intents = detect_intents(query)
            categories: List[str] = []
            for intent in intents:
                for cat in INTENT_CATEGORY_FILTERS.get(intent, []):
                    if cat not in categories:
                        categories.append(cat)
            # Câu so sánh cần nhìn rộng hơn → nới ngưỡng similarity
            is_specific = False
            # Lấy nhiều candidate hơn vì phải phủ nhiều khía cạnh
            candidate_k = max(top_k * _CANDIDATE_MUL * len(intents), 12)
        else:
            intent      = detect_intent(query)
            categories  = INTENT_CATEGORY_FILTERS.get(intent, INTENT_CATEGORY_FILTERS["general"])
            is_specific = intent in _SPECIFIC_INTENTS
            candidate_k = max(top_k * _CANDIDATE_MUL, 12)

        try:
            f = Filter(must=[FieldCondition(key="category", match=MatchAny(any=categories))])
            chunks = self._store.search(query, top_k=candidate_k, qdrant_filter=f)
        except Exception as exc:
            logger.warning(f"Search có filter lỗi ({exc}) → search không filter")
            chunks = self._store.search(query, top_k=candidate_k)

        if not chunks:
            return []

        min_sim  = _SIM_SPECIFIC if is_specific else _SIM_GENERAL
        filtered = [c for c in chunks if c["similarity"] >= min_sim] or chunks

        def _score(c: Dict) -> float:
            prio = max(1, min(5, int(c["metadata"].get("source_priority", 4))))
            return _W_SEMANTIC * c["similarity"] + _W_PRIORITY * ((6 - prio) / 5.0)

        # Với câu so sánh: ưu tiên đa dạng category trong top_k để không
        # bị 1 category áp đảo (ví dụ toàn chunk pregnancy, thiếu diagnosis)
        if is_comparison_query(query) and len(categories) > 1:
            reranked = self._diversify_by_category(filtered, top_k, _score)
        else:
            reranked = sorted(filtered, key=_score, reverse=True)[:top_k]

        logger.debug(
            f"  query='{query[:50]}' | comparison={is_comparison_query(query)} "
            f"| categories={categories} | candidates={len(chunks)} "
            f"→ filtered={len(filtered)} → top={len(reranked)}"
        )
        return reranked

    @staticmethod
    def _diversify_by_category(chunks: List[Dict], top_k: int, score_fn) -> List[Dict]:
        """
        Round-robin lấy chunk tốt nhất của từng category trước,
        đảm bảo câu so sánh có đủ đại diện mỗi khía cạnh thay vì
        bị 1 category chiếm hết top_k.
        """
        by_category: Dict[str, List[Dict]] = {}
        for c in chunks:
            cat = c["metadata"].get("category", "general")
            by_category.setdefault(cat, []).append(c)
        for cat in by_category:
            by_category[cat].sort(key=score_fn, reverse=True)

        result: List[Dict] = []
        cat_keys = list(by_category.keys())
        idx = 0
        while len(result) < top_k and any(by_category[k] for k in cat_keys):
            cat = cat_keys[idx % len(cat_keys)]
            if by_category[cat]:
                result.append(by_category[cat].pop(0))
            idx += 1
        # Sắp lại theo score để chunk liên quan nhất vẫn đứng đầu
        result.sort(key=score_fn, reverse=True)
        return result
