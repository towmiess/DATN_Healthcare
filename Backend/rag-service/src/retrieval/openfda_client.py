"""
openfda_client.py
=================
Client cho OpenFDA Drug Label API — hoàn toàn miễn phí, không cần API key.
Rate limit: 240 req/phút (không cần key), 1000 req/phút (có key).

Tính năng:
  - Tra cứu nhãn thuốc (indications, warnings, dosage, interactions)
  - Tìm tên generic/brand của thuốc
  - Tra cứu adverse events (báo cáo tác dụng phụ thực tế)
  - Cache 7 ngày (nhãn thuốc rất ít thay đổi)
  - Fallback sang tên generic nếu không tìm được brand name

OpenFDA docs: https://open.fda.gov/apis/drug/label/
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx

log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────
FDA_BASE      = "https://api.fda.gov"
RXNORM_BASE   = "https://rxnav.nlm.nih.gov/REST"
FDA_API_KEY   = os.getenv("FDA_API_KEY", "")   # optional
REQUEST_DELAY = 0.3   # 3 req/s an toàn

# Giới hạn độ dài mỗi section để không overflow context window
MAX_SECTION_LEN = 800


# ══════════════════════════════════════════════════════════════
# Drug name aliases — map tên VN/brand → generic
# ══════════════════════════════════════════════════════════════

DRUG_ALIASES: dict[str, str] = {
    # Brand → Generic
    "glucophage": "metformin",
    "januvia":    "sitagliptin",
    "jardiance":  "empagliflozin",
    "farxiga":    "dapagliflozin",
    "forxiga":    "dapagliflozin",
    "invokana":   "canagliflozin",
    "ozempic":    "semaglutide",
    "wegovy":     "semaglutide",
    "rybelsus":   "semaglutide",
    "victoza":    "liraglutide",
    "trulicity":  "dulaglutide",
    "byetta":     "exenatide",
    "lantus":     "insulin glargine",
    "toujeo":     "insulin glargine",
    "levemir":    "insulin detemir",
    "tresiba":    "insulin degludec",
    "humalog":    "insulin lispro",
    "novolog":    "insulin aspart",
    "novorapid":  "insulin aspart",
    "actos":      "pioglitazone",
    "tradjenta":  "linagliptin",
    "onglyza":    "saxagliptin",
    "amaryl":     "glimepiride",
    "diamicron":  "gliclazide",
    # Vietnamese generic names
    "thuốc tiểu đường":      "metformin",   # fallback
    "thuốc hạ đường huyết":  "metformin",
}


def normalize_drug_name(name: str) -> str:
    """Chuẩn hóa tên thuốc: lowercase, bỏ dấu câu, map alias."""
    n = name.lower().strip()
    n = re.sub(r"[^\w\s-]", "", n)
    return DRUG_ALIASES.get(n, n)


# ══════════════════════════════════════════════════════════════
# Data models
# ══════════════════════════════════════════════════════════════

@dataclass
class DrugLabel:
    """Thông tin nhãn thuốc từ OpenFDA."""
    drug_name:        str
    generic_name:     str
    brand_names:      list[str]
    indications:      str   # chỉ định điều trị
    dosage:           str   # liều dùng
    warnings:         str   # cảnh báo
    contraindications: str  # chống chỉ định
    interactions:     str   # tương tác thuốc
    adverse_reactions: str  # tác dụng phụ
    manufacturer:     str
    ndc:              str   # National Drug Code
    source_url:       str = "https://open.fda.gov/drug/label/"
    extra_sections:   dict = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not any([
            self.indications, self.dosage, self.warnings,
            self.contraindications, self.interactions,
        ])

    def to_rag_text(self) -> str:
        """Format cho LLM context."""
        brands = ", ".join(self.brand_names[:3]) if self.brand_names else "N/A"
        parts = [
            f"[Thông tin thuốc — OpenFDA]",
            f"Tên generic: {self.generic_name}",
            f"Tên thương mại: {brands}",
            f"Nhà sản xuất: {self.manufacturer}",
            "",
        ]

        sections = [
            ("Chỉ định (Indications)", self.indications),
            ("Liều dùng (Dosage)",     self.dosage),
            ("Cảnh báo (Warnings)",    self.warnings),
            ("Chống chỉ định",         self.contraindications),
            ("Tương tác thuốc",        self.interactions),
            ("Tác dụng phụ",           self.adverse_reactions),
        ]

        for title, content in sections:
            if content and content.strip():
                truncated = content[:MAX_SECTION_LEN]
                if len(content) > MAX_SECTION_LEN:
                    truncated += "…"
                parts.append(f"【{title}】\n{truncated}\n")

        parts.append(f"Nguồn: {self.source_url}")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "drug_name":         self.drug_name,
            "generic_name":      self.generic_name,
            "brand_names":       self.brand_names,
            "indications":       self.indications[:500] if self.indications else "",
            "dosage":            self.dosage[:500]      if self.dosage else "",
            "warnings":          self.warnings[:500]    if self.warnings else "",
            "contraindications": self.contraindications[:300] if self.contraindications else "",
            "interactions":      self.interactions[:300] if self.interactions else "",
            "adverse_reactions": self.adverse_reactions[:300] if self.adverse_reactions else "",
            "source_url":        self.source_url,
        }


@dataclass
class AdverseEventSummary:
    """Tóm tắt tác dụng phụ từ FDA FAERS."""
    drug_name: str
    total_reports: int
    top_reactions: list[dict]   # [{"term": str, "count": int}]

    def to_rag_text(self) -> str:
        if not self.top_reactions:
            return ""
        reactions_str = "\n".join(
            f"  - {r['term']}: {r['count']:,} báo cáo"
            for r in self.top_reactions[:8]
        )
        return (
            f"[Báo cáo tác dụng phụ thực tế — FDA FAERS]\n"
            f"Thuốc: {self.drug_name}\n"
            f"Tổng báo cáo: {self.total_reports:,}\n"
            f"Tác dụng phụ thường gặp nhất:\n{reactions_str}\n"
            f"Nguồn: https://open.fda.gov/drug/event/"
        )


# ══════════════════════════════════════════════════════════════
# API helpers
# ══════════════════════════════════════════════════════════════

def _fda_params(**kwargs) -> dict:
    params = {**kwargs}
    if FDA_API_KEY:
        params["api_key"] = FDA_API_KEY
    return params


def _extract_first(data: list, max_len: int = MAX_SECTION_LEN) -> str:
    """Lấy phần tử đầu tiên của list, cắt ngắn nếu cần."""
    if not data or not isinstance(data, list):
        return ""
    text = str(data[0]).strip()
    return text[:max_len] if len(text) > max_len else text


def _clean_fda_text(text: str) -> str:
    """Làm sạch text FDA: bỏ HTML tags, chuẩn hóa whitespace."""
    text = re.sub(r"<[^>]+>", " ", text)           # bỏ HTML tags
    text = re.sub(r"\s{2,}", " ", text)             # nhiều space → 1
    text = re.sub(r"\n{2,}", "\n", text)            # nhiều newline → 1
    text = re.sub(r"[^\x00-\x7F\u00C0-\u024F]", "", text)  # bỏ ký tự lạ
    return text.strip()


async def resolve_via_rxnorm(name: str, client: httpx.AsyncClient) -> Optional[str]:
    """
    Dùng khi OpenFDA KHÔNG tìm thấy thuốc theo tên đã cho — thường là biệt dược
    nước ngoài/Việt Nam (vd: "Atoris" của Zentiva) không đăng ký dưới tên đó
    tại Mỹ. RxNorm (thư viện NIH, miễn phí, không cần key) ánh xạ brand name
    → hoạt chất (ingredient) chuẩn quốc tế, sau đó dùng tên hoạt chất đó để
    tra lại OpenFDA (vd: Atoris → atorvastatin → tìm được nhãn FDA).
    """
    try:
        await asyncio.sleep(REQUEST_DELAY)
        resp = await client.get(
            f"{RXNORM_BASE}/drugs.json",
            params={"name": name},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
        groups = (data.get("drugGroup") or {}).get("conceptGroup") or []
        for g in groups:
            if g.get("tty") == "IN":   # IN = Ingredient (hoạt chất)
                props = g.get("conceptProperties") or []
                if props:
                    ingredient = props[0]["name"].lower()
                    log.info(f"🔗 RxNorm: '{name}' → hoạt chất '{ingredient}'")
                    return ingredient
        return None
    except Exception as e:
        log.warning(f"RxNorm resolve lỗi cho '{name}': {e}")
        return None


# ══════════════════════════════════════════════════════════════
# Drug Label API
# ══════════════════════════════════════════════════════════════

async def fetch_drug_label(
    drug_name: str,
    client: httpx.AsyncClient,
) -> Optional[DrugLabel]:
    """
    Tra cứu nhãn thuốc từ OpenFDA Drug Label API.
    Thử song song 3 field (generic_name/brand_name/substance_name) —
    trước đây làm tuần tự với timeout 15s/field → tối đa 45s nếu FDA API
    chậm/không phản hồi, khiến câu hỏi về thuốc bị "treo" không trả lời.
    """
    generic = normalize_drug_name(drug_name)

    async def _try(search_field: str, search_val: str) -> Optional[DrugLabel]:
        try:
            await asyncio.sleep(REQUEST_DELAY)
            resp = await client.get(
                f"{FDA_BASE}/drug/label.json",
                params=_fda_params(
                    search=f'{search_field}:"{search_val}"',
                    limit=1,
                ),
                timeout=6,   # FDA API bình thường trả lời <1s; không cần chờ 15s
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()

            data = resp.json()
            results = data.get("results", [])
            if not results:
                return None

            r = results[0]
            openfda = r.get("openfda", {})

            label = DrugLabel(
                drug_name        = drug_name,
                generic_name     = ", ".join(openfda.get("generic_name", [generic])),
                brand_names      = openfda.get("brand_name", []),
                indications      = _clean_fda_text(_extract_first(r.get("indications_and_usage", []))),
                dosage           = _clean_fda_text(_extract_first(r.get("dosage_and_administration", []))),
                warnings         = _clean_fda_text(_extract_first(
                                        r.get("warnings_and_cautions")
                                        or r.get("warnings", [])
                                    )),
                contraindications= _clean_fda_text(_extract_first(r.get("contraindications", []))),
                interactions     = _clean_fda_text(_extract_first(r.get("drug_interactions", []))),
                adverse_reactions= _clean_fda_text(_extract_first(r.get("adverse_reactions", []))),
                manufacturer     = ", ".join(openfda.get("manufacturer_name", ["N/A"])[:2]),
                ndc              = ", ".join(openfda.get("product_ndc", ["N/A"])[:2]),
            )

            return label if not label.is_empty() else None

        except httpx.HTTPStatusError as e:
            log.warning(f"FDA API {e.response.status_code} for {search_val}")
            return None
        except Exception as e:
            log.error(f"FDA label error ({search_field}={search_val}): {e}")
            return None

    tasks = [
        _try("openfda.generic_name",    generic),
        _try("openfda.brand_name",      drug_name.upper()),
        _try("openfda.substance_name",  generic.upper()),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, DrugLabel):
            log.info(f"✅ FDA label found: {r.generic_name}")
            return r

    # ── Fallback: không có trong OpenFDA dưới tên đã cho (thường là biệt
    #    dược nước ngoài/VN) → ánh xạ qua RxNorm sang hoạt chất rồi thử lại
    ingredient = await resolve_via_rxnorm(drug_name, client)
    if ingredient and ingredient != generic:
        fallback = await _try("openfda.generic_name", ingredient)
        if fallback:
            fallback.drug_name = drug_name   # giữ tên gốc người dùng hỏi
            log.info(f"✅ FDA label found via RxNorm: {fallback.generic_name}")
            return fallback

    log.warning(f"FDA: không tìm thấy nhãn thuốc cho '{drug_name}' (kể cả qua RxNorm)")
    return None


# ══════════════════════════════════════════════════════════════
# Adverse Events API (FAERS)
# ══════════════════════════════════════════════════════════════

async def fetch_adverse_events(
    drug_name: str,
    client: httpx.AsyncClient,
    limit: int = 10,
) -> Optional[AdverseEventSummary]:
    """
    Lấy tóm tắt tác dụng phụ từ FDA FAERS (báo cáo thực tế từ bệnh nhân/bác sĩ).
    Useful cho câu hỏi: "Thuốc X có tác dụng phụ gì trong thực tế?"
    """
    generic = normalize_drug_name(drug_name)

    try:
        await asyncio.sleep(REQUEST_DELAY)
        resp = await client.get(
            f"{FDA_BASE}/drug/event.json",
            params=_fda_params(
                search=f'patient.drug.openfda.generic_name:"{generic}"',
                count="patient.reaction.reactionmeddrapt.exact",
                limit=limit,
            ),
            timeout=6,
        )

        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        data = resp.json()
        results = data.get("results", [])
        meta    = data.get("meta", {}).get("results", {})

        if not results:
            return None

        top_reactions = [
            {"term": r["term"], "count": r["count"]}
            for r in results[:limit]
        ]

        # Tổng số báo cáo (từ meta hoặc đếm)
        total = meta.get("total", sum(r["count"] for r in results))

        log.info(f"✅ FDA FAERS: {len(top_reactions)} reactions cho '{generic}'")
        return AdverseEventSummary(
            drug_name=generic,
            total_reports=total,
            top_reactions=top_reactions,
        )

    except Exception as e:
        log.warning(f"FDA FAERS error for '{drug_name}': {e}")
        return None


# ══════════════════════════════════════════════════════════════
# Main public function — dùng trong RAG pipeline
# ══════════════════════════════════════════════════════════════

async def lookup_drugs_for_rag(
    drug_names: list[str],
    include_adverse_events: bool = True,
) -> dict[str, dict]:
    """
    Tra cứu nhiều thuốc song song.
    Trả về dict: {drug_name: {"label": DrugLabel, "adverse": AdverseEventSummary}}

    Dùng trong hybrid_retriever.py:
        fda_results = await lookup_drugs_for_rag(decision.drug_names)
        for drug, info in fda_results.items():
            if info["label"]:
                context += info["label"].to_rag_text()
            if info["adverse"]:
                context += info["adverse"].to_rag_text()
    """
    if not drug_names:
        return {}

    results = {}

    async def _noop_ae():
        return None

    async with httpx.AsyncClient(timeout=20) as client:
        async def _one(drug: str):
            label_task = fetch_drug_label(drug, client)
            ae_task = (
                fetch_adverse_events(drug, client)
                if include_adverse_events else _noop_ae()
            )
            label, ae = await asyncio.gather(
                label_task, ae_task, return_exceptions=True
            )
            if isinstance(label, Exception):
                log.error(f"Label error for {drug}: {label}")
                label = None
            if isinstance(ae, Exception):
                log.error(f"AE error for {drug}: {ae}")
                ae = None

            # Gọi web search khi:
            #  (a) OpenFDA + RxNorm không tìm thấy thuốc luôn (label=None), HOẶC
            #  (b) OpenFDA CÓ tìm thấy nhưng phần "công dụng" (indications) quá
            #      sơ sài/rỗng — tình huống rất phổ biến với nhãn SPL của thuốc
            #      generic (chỉ ghi thành phần/NSX, còn công dụng thì tham chiếu
            #      ngược lại nhãn thuốc gốc thay vì lặp lại toàn văn).
            # → web search ở đây đóng vai trò BỔ SUNG phần công dụng, không chỉ
            #   thay thế khi OpenFDA rỗng hoàn toàn.
            web_fallback = None
            indications_thin = (
                isinstance(label, DrugLabel)
                and len((label.indications or "").strip()) < 80
            )
            if label is None or indications_thin:
                from src.retrieval.web_search_client import search_drug_info
                try:
                    web_fallback = await search_drug_info(drug)
                except Exception as e:
                    log.warning(f"Web search fallback lỗi cho {drug}: {e}")

            return drug, label, ae, web_fallback

        # Chạy song song cho nhiều thuốc — mỗi thuốc tự fetch label+AE song song
        items = await asyncio.gather(
            *[_one(d) for d in drug_names], return_exceptions=True
        )

        for item in items:
            if isinstance(item, Exception):
                log.error(f"Drug lookup error: {item}")
                continue
            drug, label, ae, web_fallback = item
            results[drug] = {"label": label, "adverse": ae, "web_fallback": web_fallback}

    return results


def format_fda_context(fda_results: dict[str, dict]) -> str:
    """Ghép tất cả FDA info (+ web fallback nếu có) thành 1 block context cho LLM."""
    parts = []
    for drug, info in fda_results.items():
        if info.get("label"):
            parts.append(info["label"].to_rag_text())
        if info.get("adverse"):
            parts.append(info["adverse"].to_rag_text())
        if info.get("web_fallback"):
            parts.append(info["web_fallback"])
        if parts:
            parts.append("─" * 40)
    return "\n\n".join(parts)


# ══════════════════════════════════════════════════════════════
# CLI test
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    drug = sys.argv[1] if len(sys.argv) > 1 else "metformin"
    print(f"\n🔍 Tra cứu FDA: '{drug}'")
    print("─" * 60)

    async def main():
        results = await lookup_drugs_for_rag([drug], include_adverse_events=True)
        for d, info in results.items():
            if info["label"]:
                print(info["label"].to_rag_text())
            else:
                print(f"❌ Không tìm thấy nhãn thuốc cho '{d}'")

            if info["adverse"]:
                print("\n" + info["adverse"].to_rag_text())

    asyncio.run(main())
