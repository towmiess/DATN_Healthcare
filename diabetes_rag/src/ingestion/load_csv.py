"""Load structured food databases (USDA FoodData CSV, GI database CSV)."""
import pandas as pd
from pathlib import Path
from typing import List
from langchain_core.documents import Document
from rich.console import Console

console = Console()


def load_usda_csv(csv_path: str | Path, max_rows: int = None) -> List[Document]:
    """
    Convert USDA FoodData CSV into Documents.
    Each row = 1 food item = 1 Document (no chunking needed).
    """
    df = pd.read_csv(csv_path, low_memory=False)
    if max_rows:
        df = df.head(max_rows)

    # Normalize column names (USDA exports vary)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    docs: List[Document] = []
    for _, row in df.iterrows():
        name        = str(row.get("description", row.get("name", "Unknown food")))
        calories    = row.get("energy_kcal", row.get("calories", "N/A"))
        carbs       = row.get("carbohydrate_g", row.get("carbs", "N/A"))
        fiber       = row.get("fiber_g", row.get("fiber", "N/A"))
        protein     = row.get("protein_g", row.get("protein", "N/A"))
        fat         = row.get("total_fat_g", row.get("fat", "N/A"))
        food_group  = row.get("food_group", row.get("category", "General"))

        text = (
            f"Food: {name}\n"
            f"Category: {food_group}\n"
            f"Per 100g — Calories: {calories} kcal | "
            f"Carbohydrates: {carbs}g | Fiber: {fiber}g | "
            f"Protein: {protein}g | Fat: {fat}g"
        )
        docs.append(Document(
            page_content=text,
            metadata={
                "source": "USDA FoodData Central",
                "doc_type": "food_database",
                "topic": "nutrition",
                "language": "en",
                "food_name": name,
                "food_group": str(food_group),
            }
        ))

    console.print(f"[green]✓[/green] Loaded {len(docs)} food records from USDA CSV")
    return docs


def load_gi_csv(csv_path: str | Path) -> List[Document]:
    """
    Load Glycemic Index database CSV.
    Format: food_name, gi_value, gl_value, serving_size, category
    """
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    docs: List[Document] = []
    for _, row in df.iterrows():
        name     = str(row.get("food_name", row.get("food", "Unknown")))
        gi       = row.get("gi_value", row.get("gi", "N/A"))
        gl       = row.get("gl_value", row.get("gl", "N/A"))
        serving  = row.get("serving_size", "100g")
        category = row.get("category", "General")

        # GI classification
        if gi != "N/A":
            gi_num = float(gi)
            gi_class = "Low GI (≤55)" if gi_num <= 55 else ("Medium GI (56–69)" if gi_num <= 69 else "High GI (≥70)")
        else:
            gi_class = "Unknown"

        text = (
            f"Food: {name} | Category: {category}\n"
            f"Glycemic Index (GI): {gi} — {gi_class}\n"
            f"Glycemic Load (GL): {gl} | Serving: {serving}\n"
            f"Recommendation: {'Safe for diabetics — low blood sugar impact' if gi != 'N/A' and float(gi) <= 55 else 'Consume in moderation — monitor blood sugar'}"
        )
        docs.append(Document(
            page_content=text,
            metadata={
                "source": "International GI Database",
                "doc_type": "food_database",
                "topic": "nutrition",
                "language": "en",
                "food_name": name,
                "gi_value": str(gi),
                "gi_class": gi_class,
            }
        ))

    console.print(f"[green]✓[/green] Loaded {len(docs)} GI records")
    return docs
