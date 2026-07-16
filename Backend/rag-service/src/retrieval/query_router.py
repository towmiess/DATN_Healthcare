"""
query_router.py
===============
Phân loại câu hỏi → chọn nguồn dữ liệu phù hợp.

Chiến lược phân loại (theo thứ tự ưu tiên):
  1. EMERGENCY → Qdrant + cảnh báo khẩn cấp
  2. DRUG      → Qdrant + OpenFDA (web lookup thuốc)
  4. BASIC     → Qdrant only (nhanh nhất)
  DEFAULT      → Qdrant only

PubMed đã bị loại bỏ hoàn toàn khỏi pipeline này (model không dùng
nghiên cứu khoa học, chỉ cần tra cứu thuốc qua OpenFDA + data crawl).

Mỗi route trả về RouteDecision với:
  - sources: list nguồn cần query
  - top_k: số chunks Qdrant
  - use_openfda: có gọi OpenFDA tra cứu thuốc không
  - cache_ttl: thời gian cache câu trả lời (giây)
  - is_emergency: hiện disclaimer khẩn cấp
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum



class RouteType(str, Enum):
    DRUG      = "drug"        # c?u h?i v? thu?c c? th?
    BASIC     = "basic"       # c?u h?i ph? th?ng, Qdrant ??
    EMERGENCY = "emergency"   # tri?u ch?ng nguy hi?m ? c?nh b?o ngay


@dataclass
class RouteDecision:
    route_type:    RouteType
    sources:       list[str]          # ["qdrant", "openfda"]
    top_k:         int       = 6
    use_openfda:   bool      = False
    cache_ttl:     int       = 3600   # cache c?u tr? l?i (gi?y)
    is_emergency:  bool      = False
    drug_names:    list[str] = field(default_factory=list)
    reasoning:     str       = ""     # debug: l? do ch?n route n?y

    def to_log_str(self) -> str:
        return (
            f"[{self.route_type.value.upper()}] "
            f"sources={self.sources} "
            f"drug_names={self.drug_names}"
        )
# ── Câu hỏi khẩn cấp ─────────────────────────────────────────
EMERGENCY_KEYWORDS = {
    # Hạ đường huyết nặng
    "ngất", "bất tỉnh", "mất ý thức", "hôn mê",
    "co giật", "seizure", "convulsion",
    "không tỉnh dậy", "không phản ứng",
    # Tăng đường huyết cấp
    "nhiễm toan ceton", "dka", "diabetic ketoacidosis",
    "hội chứng tăng thẩm thấu", "hhs",
    "đường huyết 500", "đường huyết 400",
    "nôn mửa liên tục", "thở nhanh", "hơi thở có mùi trái cây",
    # Tim mạch
    "đau ngực dữ dội", "khó thở đột ngột",
    "đột quỵ", "stroke", "liệt mặt",
    "nhồi máu cơ tim", "heart attack",
    "cấp cứu", "emergency", "gọi 115",
}

# ── Câu hỏi cơ bản (Qdrant đủ) ───────────────────────────────
BASIC_KEYWORDS = {
    "là gì", "what is", "định nghĩa", "definition",
    "tiểu đường type 1", "tiểu đường type 2",
    "triệu chứng tiểu đường", "symptoms",
    "ăn gì", "không ăn được", "nên ăn", "should eat",
    "chế độ ăn", "diet",
    "tập thể dục", "vận động", "exercise", "workout",
    "trái cây", "rau", "tinh bột", "carb", "carbohydrate",
    "hba1c là gì", "đường huyết bình thường",
    "phân biệt", "khác nhau giữa",
    "tiểu đường thai kỳ",
    "biến chứng tiểu đường",    # overview, không cần research
    "phòng ngừa tiểu đường",
    "xét nghiệm tiểu đường",
    "chỉ số đường huyết",
}


# ══════════════════════════════════════════════════════════════
# Drug extractor
# ══════════════════════════════════════════════════════════════


DRUG_NAMES_VI_EN = {
    # Pain relievers / antiplatelets often asked in health apps
    "aspirin", "acetylsalicylic acid", "stella aspirin",
    "ibuprofen", "paracetamol", "acetaminophen",

    # Biguanides
    "metformin", "glucophage", "fortamet",
    # Sulfonylureas
    "glipizide", "glucotrol", "glimepiride", "amaryl",
    "glyburide", "glibenclamide", "diabeta",
    "glibornuride", "gliclazide", "diamicron",
    # Thiazolidinediones
    "pioglitazone", "actos", "rosiglitazone", "avandia",
    # DPP-4 inhibitors
    "sitagliptin", "januvia", "saxagliptin", "onglyza",
    "linagliptin", "tradjenta", "alogliptin", "nesina",
    "vildagliptin", "galvus",
    # GLP-1 agonists
    "semaglutide", "ozempic", "wegovy", "rybelsus",
    "liraglutide", "victoza", "saxenda",
    "dulaglutide", "trulicity",
    "exenatide", "byetta", "bydureon",
    # SGLT-2 inhibitors
    "empagliflozin", "jardiance",
    "dapagliflozin", "farxiga", "forxiga",
    "canagliflozin", "invokana",
    "ertugliflozin", "steglatro",
    # Insulin types
    "insulin glargine", "lantus", "toujeo", "basaglar",
    "insulin detemir", "levemir",
    "insulin degludec", "tresiba",
    "insulin lispro", "humalog",
    "insulin aspart", "novolog", "novorapid",
    "insulin glulisine", "apidra",
    "nph insulin", "humulin", "novolin",
    "insulin",   # t?n chung c?a 1 nh?m thu?c, v?n tra ???c tr?n OpenFDA
}

DRUG_QUESTION_KEYWORDS = {
    "li?u", "li?u d?ng", "dosage", "dose",
    "t?c d?ng ph?", "side effect", "adverse",
    "t??ng t?c thu?c", "drug interaction",
    "u?ng l?c n?o", "when to take", "how to take",
    "qu? li?u", "overdose",
    "ch?ng ch? ??nh", "contraindication",
    "c? ch? t?c d?ng", "mechanism of action",
    "thay th? thu?c", "alternative drug",
    "thu?c m?i nh?t", "new drug",
    "fda approved", "???c ch?p thu?n",
    "thu?c ti?u ???ng", "thu?c h? ???ng", "thu?c u?ng", "thu?c ti?m",
}

MEDICATION_CONTEXT_KEYWORDS = {
    "thu?c", "drug", "medication", "vi?n", "?ng", "l?", "ti?m", "u?ng",
    "l? thu?c g?", "thu?c g?", "c? ph?i thu?c", "c?ng d?ng", "t?c d?ng",
    "li?u d?ng", "u?ng l?c n?o", "c?ch d?ng", "ch? ??nh", "ch?ng ch? ??nh",
    "t?c d?ng ph?", "t??ng t?c", "brand name", "bi?t d??c",
}

MEDICATION_STOPWORDS = {
    "thu?c", "g?", "l?", "c?", "ph?i", "thu?cg?", "n?o", "cho", "v?i", "v?",
    "u?ng", "ti?m", "tr??c", "sau", "l?c", "n?o", "t?t", "nh?t", "c?ng", "d?ng",
    "t?c", "d?ng", "ph?", "li?u", "d?ng", "c?ch", "d?ng", "tr?", "?i?u", "tr?",
    "b?nh", "???ng", "huy?t", "ti?u", "??i", "th?o", "???ng", "mg", "mcg", "ml",
    "vi?n", "?ng", "l?", "brand", "name", "bi?t", "d??c", "stella",
}


def extract_drug_names(query: str) -> list[str]:
    """Tìm tên thuốc trong câu hỏi (theo danh sách thuốc tiểu đường đã biết)."""
    q = query.lower()
    found = []
    for drug in DRUG_NAMES_VI_EN:
        if drug in q:
            found.append(drug)
    # Deduplicate và ưu tiên tên dài hơn (để "insulin glargine" > "insulin")
    found.sort(key=len, reverse=True)
    seen_prefixes = set()
    result = []
    for d in found:
        if not any(d in p for p in seen_prefixes):
            result.append(d)
            seen_prefixes.add(d)
    return result[:3]  # tối đa 3 thuốc mỗi query


# Nhận diện "Tên thuốc + liều lượng" (vd: "Atoris 10mg", "Januvia 100mg")
# → bắt được CẢ những thuốc KHÔNG nằm trong DRUG_NAMES_VI_EN (không chỉ
#   thuốc tiểu đường) để route sang DRUG + tra cứu realtime qua OpenFDA/RxNorm,
#   thay vì rơi vào route BASIC (chỉ Qdrant) và trả lời "không có thông tin".
DRUG_DOSAGE_PATTERN = re.compile(
    r"\b([A-ZĐ][a-zà-ỹăâêôơư]{2,})\s*\d{1,4}(?:[.,]\d+)?\s*"
    r"(?:mg|mcg|g|ml|iu|ui|đơn vị)\b",
    re.IGNORECASE,
)


def extract_drug_candidates(query: str, allow_brand_heuristics: bool = False) -> list[str]:
    """
    Kết hợp whitelist (extract_drug_names) + pattern "tên + liều lượng"
    để tìm TẤT CẢ tên thuốc khả nghi trong câu hỏi, không giới hạn ở
    danh sách thuốc tiểu đường đã biết trước.
    """
    found = extract_drug_names(query)
    for m in DRUG_DOSAGE_PATTERN.finditer(query):
        name = m.group(1).lower()
        if name not in found and len(name) >= 3:
            found.append(name)

    m = re.search(r"\bthuốc\s+([A-Za-zÀ-ỹ0-9][\wÀ-ỹ0-9-]{2,})", query, flags=re.IGNORECASE)
    if m:
        candidate = m.group(1).lower()
        if candidate not in found:
            found.append(candidate)

    # Brand-name heuristic: nhận diện tên thuốc thương mại như Atoris, Mixtard 30,
    # Glucophage 500mg... nhưng chỉ bật khi câu hỏi có ngữ cảnh thuốc.
    if allow_brand_heuristics:
        raw_tokens = re.findall(r"[A-Za-zÀ-ỹ0-9][\wÀ-ỹ0-9-]{2,}", query)
        for index, token in enumerate(raw_tokens):
            normalized = token.strip(".,;:!?()[]{}\"'").lower()
            if not normalized or normalized in MEDICATION_STOPWORDS:
                continue
            if any(ch.isdigit() for ch in normalized):
                if normalized not in found:
                    found.append(normalized)
                continue
            if token[:1].isupper() and any(ch.isalpha() for ch in token) and len(normalized) >= 4:
                if normalized not in found:
                    found.append(normalized)

    return found[:3]


# ══════════════════════════════════════════════════════════════
# Scorer — tính điểm cho từng route
# ══════════════════════════════════════════════════════════════

def _score(query: str, keywords: set) -> int:
    """Đếm số keyword khớp trong query."""
    q = query.lower()
    return sum(1 for kw in keywords if kw in q)


# ══════════════════════════════════════════════════════════════
# Main router
# ══════════════════════════════════════════════════════════════

class QueryRouter:
    """
    Phân loại câu hỏi và trả về RouteDecision.

    Dùng:
        router = QueryRouter()
        decision = router.route("metformin uống lúc nào?")
        print(decision.to_log_str())
        # → [DRUG] sources=['qdrant', 'openfda'] drug_names=['metformin']
    """

    def route(self, query: str) -> RouteDecision:
        q = query.strip()

        # ── Ưu tiên 1: Khẩn cấp ──────────────────────────────
        emergency_score = _score(q, EMERGENCY_KEYWORDS)
        if emergency_score >= 1:
            return RouteDecision(
                route_type   = RouteType.EMERGENCY,
                sources      = ["qdrant"],
                top_k        = 4,
                cache_ttl    = 300,   # cache ngắn hơn cho khẩn cấp
                is_emergency = True,
                reasoning    = f"emergency keywords: {emergency_score}",
            )

        # ── Ưu tiên 2: Thuốc ─────────────────────────────────
        q_lower = q.lower()
        drug_trigger_phrases = (
            "thuốc", "drug", "medication", "liều", "liều dùng", "dose", "dosage",
            "tác dụng phụ", "tương tác thuốc", "chống chỉ định", "cơ chế tác dụng",
            "uống lúc nào", "how to take", "when to take", "cách dùng", "chỉ định",
            "công dụng", "quá liều", "overdose", "thuốc tiêm", "thuốc uống",
        )
        med_context_hit = any(phrase in q_lower for phrase in drug_trigger_phrases)
        allow_brand_heuristics = med_context_hit or _score(q, DRUG_QUESTION_KEYWORDS) >= 1 or bool(DRUG_DOSAGE_PATTERN.search(q))
        drug_names    = extract_drug_candidates(q, allow_brand_heuristics=allow_brand_heuristics)
        drug_name_hit = len(drug_names) > 0
        drug_kw_hit   = _score(q, DRUG_QUESTION_KEYWORDS) >= 1
        dosage_hit    = bool(DRUG_DOSAGE_PATTERN.search(q))
        if drug_name_hit or dosage_hit or drug_kw_hit or med_context_hit:
            return RouteDecision(
                route_type  = RouteType.DRUG,
                sources     = ["qdrant", "openfda"],
                top_k       = 4,
                use_openfda = True,
                cache_ttl   = 7200,   # thuốc ít thay đổi → cache 2h
                drug_names  = drug_names,
                reasoning   = f"drugs={drug_names}, kw_hit={drug_kw_hit}, dosage_pattern={dosage_hit}, med_context={med_context_hit}",
            )

        # ── Basic (Qdrant only) ───────────────────────────────
        basic_score = _score(q, BASIC_KEYWORDS)
        if basic_score >= 1:
            return RouteDecision(
                route_type = RouteType.BASIC,
                sources    = ["qdrant"],
                top_k      = 6,
                cache_ttl  = 7200,
                reasoning  = f"basic keywords: {basic_score}",
            )

        # ── Default: fallback Qdrant only ─────────────────────
        return RouteDecision(
            route_type = RouteType.BASIC,
            sources    = ["qdrant"],
            top_k      = 6,
            cache_ttl  = 3600,
            reasoning  = "default fallback (qdrant only)",
        )


# ── Singleton để import dùng luôn ─────────────────────────────
router = QueryRouter()


# ══════════════════════════════════════════════════════════════
# CLI test
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_queries = [
        # Drug
        "Metformin uống lúc nào tốt nhất?",
        "Semaglutide có tác dụng phụ gì không?",
        "Liều insulin glargine cho người mới dùng?",
        "Thuốc Mixtard 30 là thuốc gì",
        "Aspirin Stella 81mg là thuốc gì"
        # Research
        "So sánh hiệu quả giữa SGLT2 và DPP4 inhibitor?",
        "Nghiên cứu mới nhất về metformin và tim mạch?",
        # Realtime
        "Guideline ADA 2026 thay đổi gì so với 2025?",
        "Thuốc tiểu đường mới được FDA chấp thuận 2025?",
        # Basic
        "Tiểu đường type 1 khác type 2 như thế nào?",
        "HbA1c bình thường là bao nhiêu?",
        "Người tiểu đường nên ăn gì?",
        "Tiểu đường loại 2 cần bổ sung những chất gì"
        # Emergency
        "Bệnh nhân hôn mê, đường huyết 500, phải làm gì?",
        "Bị co giật sau khi tiêm insulin, cấp cứu thế nào?",
        # Hybrid
        "Biến chứng tim mạch ở người tiểu đường type 2?",
    ]

    print(f"\n{'─'*70}")
    print(f"{'QUERY':<45} {'ROUTE':<12} {'SOURCES'}")
    print(f"{'─'*70}")

    r = QueryRouter()
    for q in test_queries:
        d = r.route(q)
        print(
            f"{q[:44]:<45} "
            f"{d.route_type.value:<12} "
            f"{','.join(d.sources)}"
            f"{'  ⚠ EMERGENCY' if d.is_emergency else ''}"
            f"{'  💊 ' + str(d.drug_names) if d.drug_names else ''}"
        )
    print(f"{'─'*70}\n")
