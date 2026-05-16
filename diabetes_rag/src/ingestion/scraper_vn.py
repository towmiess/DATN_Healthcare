"""
Vietnamese Food Composition Scraper
====================================
Scrapes food nutrition data from:
  1. Viện Dinh Dưỡng (National Institute of Nutrition, Vietnam)
     → viendinhduong.vn/vi/bang-thanh-phan-thuc-pham-viet-nam.html
  2. MOH Vietnam nutrition tables
  3. Supplementary: common Vietnamese dishes with estimated GI values

Outputs:
  - data/processed/vn_foods.csv
  - data/processed/vn_foods_documents.json   (ready for RAG ingestion)

Run:
  python -m src.ingestion.scraper_vn
"""

import json
import time
import csv
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import track

console = Console()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; DiabetesRAGBot/1.0; "
        "research-use-only; contact: your@email.com)"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ── Data model ───────────────────────────────────────────────────────────────
@dataclass
class VietnameseFoodItem:
    name_vi: str           # Vietnamese name (e.g. "Cơm trắng")
    name_en: str           # English name   (e.g. "White rice")
    category_vi: str       # Food group in Vietnamese
    category_en: str       # Food group in English
    serving_g: float       # Standard serving in grams
    calories_kcal: float
    carbs_g: float
    fiber_g: float
    protein_g: float
    fat_g: float
    gi_value: Optional[int]     # Glycemic Index (if known)
    gl_value: Optional[float]   # Glycemic Load  (if known)
    gi_class: str               # "Low" | "Medium" | "High" | "Unknown"
    diabetes_note: str          # Plain-language advice
    source: str


def classify_gi(gi: Optional[int]) -> str:
    if gi is None:
        return "Unknown"
    if gi <= 55:
        return "Low"
    if gi <= 69:
        return "Medium"
    return "High"


def make_diabetes_note(item: "VietnameseFoodItem") -> str:
    """Generate a plain-language diabetes suitability note."""
    if item.gi_class == "Low":
        return (
            f"{item.name_vi} có GI thấp ({item.gi_value}) — phù hợp cho người tiểu đường. "
            f"Mỗi khẩu phần {item.serving_g}g cung cấp {item.carbs_g}g carbs."
        )
    if item.gi_class == "Medium":
        return (
            f"{item.name_vi} có GI trung bình ({item.gi_value}) — ăn vừa phải, "
            f"kết hợp với rau xanh và protein để giảm tác động đường huyết."
        )
    if item.gi_class == "High":
        return (
            f"{item.name_vi} có GI cao ({item.gi_value}) — hạn chế với người tiểu đường. "
            f"Nên thay bằng các lựa chọn GI thấp hơn hoặc giảm khẩu phần."
        )
    return (
        f"{item.name_vi}: {item.carbs_g}g carbs/{item.serving_g}g. "
        f"Chưa có dữ liệu GI — theo dõi đường huyết sau khi ăn."
    )


# ── Built-in Vietnamese food database ────────────────────────────────────────
# Based on: Bảng thành phần thực phẩm Việt Nam (Viện Dinh Dưỡng, 2017)
# + International GI Tables + Vietnamese clinical nutrition guidelines
BUILTIN_VN_FOODS: List[Dict] = [
    # ── Grains / Staples ─────────────────────────────────────────────────────
    {"name_vi":"Cơm trắng","name_en":"White rice (cooked)","category_vi":"Ngũ cốc","category_en":"Grains","serving_g":150,"calories_kcal":195,"carbs_g":43,"fiber_g":0.4,"protein_g":4,"fat_g":0.4,"gi_value":72,"source":"VDD+IntlGI"},
    {"name_vi":"Cơm gạo lứt","name_en":"Brown rice (cooked)","category_vi":"Ngũ cốc","category_en":"Grains","serving_g":150,"calories_kcal":165,"carbs_g":34,"fiber_g":1.8,"protein_g":3.5,"fat_g":0.9,"gi_value":50,"source":"VDD+IntlGI"},
    {"name_vi":"Bánh mì trắng","name_en":"White bread","category_vi":"Bánh","category_en":"Bread","serving_g":60,"calories_kcal":159,"carbs_g":30,"fiber_g":0.8,"protein_g":5,"fat_g":1.5,"gi_value":75,"source":"IntlGI"},
    {"name_vi":"Bánh mì đen (ngũ cốc)","name_en":"Wholegrain bread","category_vi":"Bánh","category_en":"Bread","serving_g":60,"calories_kcal":138,"carbs_g":24,"fiber_g":3.2,"protein_g":5.5,"fat_g":1.8,"gi_value":51,"source":"IntlGI"},
    {"name_vi":"Bún (bún bò, bún riêu)","name_en":"Rice vermicelli (cooked)","category_vi":"Ngũ cốc","category_en":"Noodles","serving_g":200,"calories_kcal":216,"carbs_g":47,"fiber_g":0.2,"protein_g":4.4,"fat_g":0.4,"gi_value":58,"source":"VDD+IntlGI"},
    {"name_vi":"Phở (bánh phở)","name_en":"Pho rice noodles (cooked)","category_vi":"Ngũ cốc","category_en":"Noodles","serving_g":200,"calories_kcal":200,"carbs_g":44,"fiber_g":0.3,"protein_g":3.8,"fat_g":0.3,"gi_value":61,"source":"VDD+IntlGI"},
    {"name_vi":"Mì tôm (mì ăn liền)","name_en":"Instant noodles","category_vi":"Ngũ cốc","category_en":"Noodles","serving_g":85,"calories_kcal":375,"carbs_g":52,"fiber_g":2,"protein_g":8,"fat_g":14,"gi_value":47,"source":"IntlGI"},
    {"name_vi":"Khoai lang","name_en":"Sweet potato (boiled)","category_vi":"Củ","category_en":"Root vegetables","serving_g":150,"calories_kcal":130,"carbs_g":30,"fiber_g":3.8,"protein_g":2.3,"fat_g":0.1,"gi_value":44,"source":"IntlGI"},
    {"name_vi":"Khoai tây luộc","name_en":"White potato (boiled)","category_vi":"Củ","category_en":"Root vegetables","serving_g":150,"calories_kcal":116,"carbs_g":27,"fiber_g":2.4,"protein_g":2.5,"fat_g":0.1,"gi_value":78,"source":"IntlGI"},
    {"name_vi":"Sắn (khoai mì)","name_en":"Cassava (boiled)","category_vi":"Củ","category_en":"Root vegetables","serving_g":100,"calories_kcal":160,"carbs_g":38,"fiber_g":1.8,"protein_g":1.4,"fat_g":0.3,"gi_value":46,"source":"VDD"},
    # ── Proteins ─────────────────────────────────────────────────────────────
    {"name_vi":"Thịt gà (không da, luộc)","name_en":"Chicken breast (cooked, skinless)","category_vi":"Thịt","category_en":"Poultry","serving_g":100,"calories_kcal":165,"carbs_g":0,"fiber_g":0,"protein_g":31,"fat_g":3.6,"gi_value":0,"source":"VDD"},
    {"name_vi":"Thịt heo nạc","name_en":"Lean pork","category_vi":"Thịt","category_en":"Meat","serving_g":100,"calories_kcal":143,"carbs_g":0,"fiber_g":0,"protein_g":26,"fat_g":3.5,"gi_value":0,"source":"VDD"},
    {"name_vi":"Cá tra","name_en":"Pangasius fish (steamed)","category_vi":"Hải sản","category_en":"Fish","serving_g":100,"calories_kcal":128,"carbs_g":0,"fiber_g":0,"protein_g":18,"fat_g":6,"gi_value":0,"source":"VDD"},
    {"name_vi":"Cá ngừ","name_en":"Tuna (canned in water)","category_vi":"Hải sản","category_en":"Fish","serving_g":100,"calories_kcal":116,"carbs_g":0,"fiber_g":0,"protein_g":26,"fat_g":1,"gi_value":0,"source":"IntlGI"},
    {"name_vi":"Trứng gà","name_en":"Chicken egg (whole)","category_vi":"Trứng","category_en":"Eggs","serving_g":60,"calories_kcal":86,"carbs_g":0.6,"fiber_g":0,"protein_g":7.5,"fat_g":5.8,"gi_value":0,"source":"VDD"},
    {"name_vi":"Đậu hũ (tàu hũ)","name_en":"Tofu (firm)","category_vi":"Đậu","category_en":"Legumes","serving_g":100,"calories_kcal":76,"carbs_g":1.9,"fiber_g":0.3,"protein_g":8.1,"fat_g":4.2,"gi_value":15,"source":"IntlGI"},
    {"name_vi":"Đậu xanh (nấu chín)","name_en":"Mung beans (cooked)","category_vi":"Đậu","category_en":"Legumes","serving_g":100,"calories_kcal":105,"carbs_g":19,"fiber_g":7.6,"protein_g":7.0,"fat_g":0.4,"gi_value":25,"source":"IntlGI"},
    # ── Vegetables ───────────────────────────────────────────────────────────
    {"name_vi":"Rau muống luộc","name_en":"Water spinach (cooked)","category_vi":"Rau","category_en":"Vegetables","serving_g":100,"calories_kcal":19,"carbs_g":3.1,"fiber_g":2.1,"protein_g":2.6,"fat_g":0.2,"gi_value":None,"source":"VDD"},
    {"name_vi":"Cải xanh","name_en":"Chinese cabbage","category_vi":"Rau","category_en":"Vegetables","serving_g":100,"calories_kcal":16,"carbs_g":2.8,"fiber_g":1.6,"protein_g":1.6,"fat_g":0.2,"gi_value":None,"source":"VDD"},
    {"name_vi":"Đậu bắp (bắp chuối)","name_en":"Okra","category_vi":"Rau","category_en":"Vegetables","serving_g":100,"calories_kcal":33,"carbs_g":7,"fiber_g":3.2,"protein_g":1.9,"fat_g":0.2,"gi_value":20,"source":"IntlGI"},
    {"name_vi":"Cà chua","name_en":"Tomato","category_vi":"Rau","category_en":"Vegetables","serving_g":100,"calories_kcal":18,"carbs_g":3.9,"fiber_g":1.2,"protein_g":0.9,"fat_g":0.2,"gi_value":15,"source":"IntlGI"},
    {"name_vi":"Khổ qua (mướp đắng)","name_en":"Bitter melon","category_vi":"Rau","category_en":"Vegetables","serving_g":100,"calories_kcal":17,"carbs_g":3.7,"fiber_g":2.8,"protein_g":1.0,"fat_g":0.2,"gi_value":None,"source":"VDD"},
    # ── Fruits ───────────────────────────────────────────────────────────────
    {"name_vi":"Ổi","name_en":"Guava","category_vi":"Trái cây","category_en":"Fruits","serving_g":100,"calories_kcal":68,"carbs_g":14,"fiber_g":5.4,"protein_g":2.6,"fat_g":0.9,"gi_value":12,"source":"IntlGI"},
    {"name_vi":"Bưởi","name_en":"Pomelo","category_vi":"Trái cây","category_en":"Fruits","serving_g":100,"calories_kcal":38,"carbs_g":9.6,"fiber_g":1.1,"protein_g":0.7,"fat_g":0.1,"gi_value":25,"source":"IntlGI"},
    {"name_vi":"Táo","name_en":"Apple","category_vi":"Trái cây","category_en":"Fruits","serving_g":100,"calories_kcal":52,"carbs_g":14,"fiber_g":2.4,"protein_g":0.3,"fat_g":0.2,"gi_value":36,"source":"IntlGI"},
    {"name_vi":"Xoài chín","name_en":"Ripe mango","category_vi":"Trái cây","category_en":"Fruits","serving_g":100,"calories_kcal":60,"carbs_g":15,"fiber_g":1.6,"protein_g":0.8,"fat_g":0.4,"gi_value":51,"source":"IntlGI"},
    {"name_vi":"Chuối chín","name_en":"Ripe banana","category_vi":"Trái cây","category_en":"Fruits","serving_g":100,"calories_kcal":89,"carbs_g":23,"fiber_g":2.6,"protein_g":1.1,"fat_g":0.3,"gi_value":51,"source":"IntlGI"},
    {"name_vi":"Dưa hấu","name_en":"Watermelon","category_vi":"Trái cây","category_en":"Fruits","serving_g":150,"calories_kcal":46,"carbs_g":11,"fiber_g":0.6,"protein_g":0.9,"fat_g":0.2,"gi_value":76,"source":"IntlGI"},
    # ── Dairy / Beverages ─────────────────────────────────────────────────────
    {"name_vi":"Sữa tươi không đường","name_en":"Fresh milk (unsweetened)","category_vi":"Sữa","category_en":"Dairy","serving_g":200,"calories_kcal":122,"carbs_g":9.5,"fiber_g":0,"protein_g":6.6,"fat_g":6.6,"gi_value":27,"source":"IntlGI"},
    {"name_vi":"Sữa chua không đường","name_en":"Plain yogurt (unsweetened)","category_vi":"Sữa","category_en":"Dairy","serving_g":150,"calories_kcal":92,"carbs_g":11,"fiber_g":0,"protein_g":7.5,"fat_g":2.3,"gi_value":17,"source":"IntlGI"},
    {"name_vi":"Nước dừa","name_en":"Coconut water","category_vi":"Đồ uống","category_en":"Beverages","serving_g":250,"calories_kcal":46,"carbs_g":9,"fiber_g":2.6,"protein_g":1.7,"fat_g":0.5,"gi_value":None,"source":"VDD"},
]


def build_food_items() -> List[VietnameseFoodItem]:
    """Convert raw dicts → typed FoodItem objects with GI class + diabetes note."""
    items = []
    for d in BUILTIN_VN_FOODS:
        gi = d.get("gi_value")
        gi_class = classify_gi(gi)
        # Calculate GL = (GI × carbs_g) / 100
        gl = round((gi * d["carbs_g"]) / 100, 1) if gi else None

        item = VietnameseFoodItem(
            name_vi=d["name_vi"],
            name_en=d["name_en"],
            category_vi=d["category_vi"],
            category_en=d["category_en"],
            serving_g=d["serving_g"],
            calories_kcal=d["calories_kcal"],
            carbs_g=d["carbs_g"],
            fiber_g=d["fiber_g"],
            protein_g=d["protein_g"],
            fat_g=d["fat_g"],
            gi_value=gi,
            gl_value=gl,
            gi_class=gi_class,
            diabetes_note="",
            source=d["source"],
        )
        item.diabetes_note = make_diabetes_note(item)
        items.append(item)
    return items


def scrape_viendinhduong() -> List[VietnameseFoodItem]:
    """
    Attempt to scrape live data from viendinhduong.vn.
    Falls back to built-in data if the site is unavailable.
    """
    url = "https://viendinhduong.vn/vi/bang-thanh-phan-thuc-pham-viet-nam.html"
    console.print(f"[blue]→[/blue] Fetching Viện Dinh Dưỡng: {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Try to find the food composition table
        tables = soup.find_all("table")
        if not tables:
            raise ValueError("No tables found on page")

        console.print(f"[green]✓[/green] Found {len(tables)} tables on page")
        # Parse first data table (structure may vary — adjust selectors as needed)
        rows = tables[0].find_all("tr")[1:]  # skip header
        scraped = []
        for row in rows[:50]:  # limit for demo
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) >= 6:
                try:
                    item = VietnameseFoodItem(
                        name_vi=cols[0], name_en=cols[0],
                        category_vi=cols[1] if len(cols) > 1 else "Chưa phân loại",
                        category_en="Uncategorized",
                        serving_g=100,
                        calories_kcal=float(cols[2]) if cols[2].replace('.','').isdigit() else 0,
                        carbs_g=float(cols[4]) if len(cols) > 4 and cols[4].replace('.','').isdigit() else 0,
                        fiber_g=0, protein_g=float(cols[3]) if len(cols)>3 and cols[3].replace('.','').isdigit() else 0,
                        fat_g=float(cols[5]) if len(cols)>5 and cols[5].replace('.','').isdigit() else 0,
                        gi_value=None, gl_value=None, gi_class="Unknown",
                        diabetes_note="", source="Viện Dinh Dưỡng (live)"
                    )
                    item.diabetes_note = make_diabetes_note(item)
                    scraped.append(item)
                except Exception:
                    continue
        if scraped:
            console.print(f"[green]✓[/green] Scraped {len(scraped)} items from live site")
            return scraped

    except Exception as e:
        console.print(f"[yellow]⚠ Live scrape failed ({e}). Using built-in database.[/yellow]")

    # Fallback to our curated built-in database
    items = build_food_items()
    console.print(f"[green]✓[/green] Built-in database: {len(items)} Vietnamese food items loaded")
    return items


def save_to_csv(items: List[VietnameseFoodItem], path: Path):
    """Save food items to CSV for inspection / further use."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=asdict(items[0]).keys())
        writer.writeheader()
        for item in items:
            writer.writerow(asdict(item))
    console.print(f"[green]✓[/green] Saved CSV → {path}")


def to_rag_documents(items: List[VietnameseFoodItem]) -> List[Dict]:
    """
    Convert food items to RAG-ready document dicts.
    Each document has:
      - page_content: rich bilingual text Claude can quote
      - metadata: structured fields for filtering
    """
    docs = []
    for item in items:
        gi_str = str(item.gi_value) if item.gi_value is not None else "Chưa có dữ liệu"
        gl_str = str(item.gl_value) if item.gl_value is not None else "N/A"

        content = (
            f"Thực phẩm: {item.name_vi} ({item.name_en})\n"
            f"Nhóm thực phẩm: {item.category_vi} ({item.category_en})\n"
            f"Khẩu phần chuẩn: {item.serving_g}g\n"
            f"Dinh dưỡng (per {item.serving_g}g):\n"
            f"  Năng lượng: {item.calories_kcal} kcal\n"
            f"  Carbohydrate: {item.carbs_g}g | Chất xơ: {item.fiber_g}g\n"
            f"  Protein: {item.protein_g}g | Chất béo: {item.fat_g}g\n"
            f"Chỉ số GI: {gi_str} ({item.gi_class} GI)\n"
            f"Chỉ số GL: {gl_str}\n"
            f"Lưu ý tiểu đường: {item.diabetes_note}\n"
            f"Nguồn: {item.source}"
        )
        docs.append({
            "page_content": content,
            "metadata": {
                "source":       "Viện Dinh Dưỡng VN",
                "doc_type":     "food_database",
                "topic":        "nutrition",
                "language":     "vi",
                "food_name_vi": item.name_vi,
                "food_name_en": item.name_en,
                "category":     item.category_en,
                "gi_value":     str(item.gi_value or ""),
                "gi_class":     item.gi_class,
                "trust_level":  "food_database",
            }
        })
    return docs


def run_scraper():
    """Main entry point — scrape, save, and export for RAG."""
    console.rule("[bold green]Vietnamese Food Composition Scraper")

    items = scrape_viendinhduong()
    time.sleep(1)  # polite delay

    # Save CSV
    csv_path = OUTPUT_DIR / "vn_foods.csv"
    save_to_csv(items, csv_path)

    # Save RAG documents JSON
    docs = to_rag_documents(items)
    json_path = OUTPUT_DIR / "vn_foods_documents.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    console.print(f"[green]✓[/green] Saved RAG documents → {json_path}")

    # Print sample
    console.rule("Sample output")
    console.print(docs[0]["page_content"])
    console.print(f"\n[dim]Metadata: {docs[0]['metadata']}[/dim]")
    console.rule()
    console.print(f"[bold green]✓ Done! {len(items)} food items ready for RAG ingestion.[/bold green]")
    return docs


if __name__ == "__main__":
    run_scraper()
