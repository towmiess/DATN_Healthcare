# 🩺 Diabetes RAG System

A production-ready Retrieval-Augmented Generation system for personalized diabetes health advice, diet planning, and lifestyle guidance — with full Vietnamese language support.

## Architecture

```
User query
    ↓
Patient profile (age, HbA1c, type, allergies, goals)
    ↓
Smart retriever (MMR + metadata filter by topic/language)
    ↓
ChromaDB vector store (ADA guidelines + USDA + Vietnamese food data)
    ↓
Claude — grounded, cited, personalized answer
```

## Quick Start

```bash
# 1. Clone & install
git clone <repo>
cd diabetes_rag
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env → add ANTHROPIC_API_KEY

# 3. Add PDF documents (ADA, WHO, etc.) to data/raw/guidelines/

# 4. Build the knowledge base
python main.py --build

# 5. Start querying
python main.py

# 6. Run evaluation
python main.py --eval
```

## Knowledge Sources

| Source | Type | Language | How to get |
|--------|------|----------|-----------|
| ADA Standards 2026 | Clinical guideline | EN | professional.diabetes.org |
| WHO Diabetes Guidelines | Clinical guideline | EN/VI | who.int/publications |
| NCBI / PubMed PMC papers | Research | EN | pmc.ncbi.nlm.nih.gov |
| USDA FoodData Central | Food database | EN | api.nal.usda.gov |
| International GI Database | Food database | EN | glycemic-index-database.com |
| Viện Dinh Dưỡng VN (built-in) | Food database | VI | Auto-scraped |
| MOH Vietnam guidelines | Clinical guideline | VI | moh.gov.vn |

## Project Structure

```
diabetes_rag/
├── config/
│   └── settings.py          # All config from .env
├── src/
│   ├── ingestion/
│   │   ├── load_pdfs.py     # PDF loader (ADA, WHO)
│   │   ├── load_csv.py      # USDA + GI CSV loader
│   │   └── scraper_vn.py    # Vietnamese food scraper ⭐
│   ├── chunking/
│   │   ├── chunker.py       # Smart per-type chunking
│   │   └── metadata_enricher.py  # Topic + language tagging
│   ├── retrieval/
│   │   ├── vectorstore.py   # ChromaDB build + load
│   │   └── retriever.py     # MMR + filtered retrieval
│   ├── generation/
│   │   ├── prompt_builder.py # Personalized Claude prompts
│   │   └── rag_chain.py     # Full RAG pipeline ⭐
│   └── evaluation/
│       ├── test_cases.py    # 25 Q&A pairs (EN + VI) ⭐
│       └── ragas_eval.py    # RAGAS-style evaluation
├── data/
│   ├── raw/                 # Place PDFs + CSVs here
│   ├── processed/           # Auto-generated (JSON, CSV)
│   └── embeddings/          # ChromaDB persisted here
├── main.py                  # Entry point
├── requirements.txt
└── .env.example
```

## Evaluation Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Faithfulness | > 85% | Answer grounded in retrieved context |
| Answer Relevance | > 85% | Answer addresses the question |
| Context Recall | > 80% | Retrieved chunks contain ground truth |
| Safety | > 95% | Appropriate medical disclaimers included |

## Vietnamese Food Database (built-in)

30 Vietnamese foods pre-loaded with:
- GI / GL values linked to International GI Tables
- Bilingual names (Vietnamese + English)
- Diabetes-specific advice in Vietnamese
- Auto-scraper for viendinhduong.vn updates

## Disclaimer

This system provides general health information only and is not a substitute for professional medical advice. Always consult a licensed doctor or registered dietitian for medical decisions.
