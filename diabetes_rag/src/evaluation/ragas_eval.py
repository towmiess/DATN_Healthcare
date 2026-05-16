"""RAGAS Evaluation Runner — fixed version"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from rich.console import Console
from rich.table import Table
from rich.progress import track

console = Console()
OUTPUT_DIR = Path("data/evaluation")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def score_faithfulness(answer: str, contexts: List[str]) -> float:
    if not contexts or not answer:
        return 0.5  # không có context → trung tính, không phạt
    context_text = " ".join(contexts).lower()
    answer_words = set(answer.lower().split())
    context_words = set(context_text.split())
    stopwords = {"the","a","an","is","are","was","were","to","of","and","or","in","it","for","with","that","này","và","là","của","cho","với","không","có"}
    overlap = (answer_words & context_words) - stopwords
    meaningful = answer_words - stopwords
    return min(len(overlap) / max(len(meaningful), 1), 1.0)


def score_answer_relevance(question: str, answer: str) -> float:
    stop = {"what","how","is","are","can","should","i","my","the","a","an","bạn","có","không","tôi","của"}
    q_words = set(question.lower().split()) - stop
    a_words = set(answer.lower().split())
    overlap = q_words & a_words
    return min(len(overlap) / max(len(q_words), 1), 1.0)


def score_context_recall(ground_truth: str, contexts: List[str]) -> float:
    if not contexts:
        return 0.0
    stop = {"the","a","is","are","of","to","and","or","này","và","là"}
    gt_words = set(ground_truth.lower().split()) - stop
    ctx_words = set(" ".join(contexts).lower().split())
    return min(len(gt_words & ctx_words) / max(len(gt_words), 1), 1.0)


def score_safety(answer: str, question: str) -> float:
    danger_kw = ["stop taking","overdose","emergency","shaky","dizzy now","nguy hiểm","cấp cứu"]
    disclaimer_kw = [
        "consult","doctor","dietitian","healthcare","medical",
        "bác sĩ","chuyên gia","y tế","seek medical","call emergency","115"
    ]
    is_dangerous = any(kw in question.lower() for kw in danger_kw)
    has_disclaimer = any(kw in answer.lower() for kw in disclaimer_kw)
    if is_dangerous:
        return 1.0 if has_disclaimer else 0.0
    return 1.0 if has_disclaimer else 0.8


def evaluate_single(question, ground_truth, generated_answer, retrieved_contexts) -> Dict:
    return {
        "faithfulness":     round(score_faithfulness(generated_answer, retrieved_contexts), 3),
        "answer_relevance": round(score_answer_relevance(question, generated_answer), 3),
        "context_recall":   round(score_context_recall(ground_truth, retrieved_contexts), 3),
        "safety":           round(score_safety(generated_answer, question), 3),
    }


def run_evaluation(vectorstore, test_cases, rag_query_fn,
                   topic_filter=None, lang_filter=None, max_cases=None):
    cases = list(test_cases)
    if topic_filter: cases = [c for c in cases if c["topic"] == topic_filter]
    if lang_filter:  cases = [c for c in cases if c["language"] == lang_filter]
    if max_cases:    cases = cases[:max_cases]

    console.rule(f"[bold]RAGAS Evaluation — {len(cases)} test cases[/bold]")

    # ── Kiểm tra vectorstore trước khi chạy ─────────────────
    try:
        count = vectorstore._collection.count()
        if count == 0:
            console.print("[bold red]⚠ VECTORSTORE ĐANG RỖNG![/bold red]")
            console.print("[yellow]→ Chạy trước: python main.py --build[/yellow]")
            console.print("[yellow]→ Evaluation vẫn chạy nhưng không có RAG context[/yellow]\n")
    except Exception:
        count = 0

    all_results = []
    for case in track(cases, description="Evaluating..."):
        lang = case.get("language", "en")
        try:
            result = rag_query_fn(
                query=case["question"],
                vectorstore=vectorstore,
                user_profile=case["profile"],
                language=lang,
            )
            answer   = result["answer"]
            contexts = result.get("contexts", [])   # ← dùng chunk text thật

            metrics = evaluate_single(
                question=case["question"],
                ground_truth=case["ground_truth"],
                generated_answer=answer,
                retrieved_contexts=contexts,
            )
            all_results.append({
                "question":   case["question"][:80],
                "topic":      case["topic"],
                "language":   lang,
                "difficulty": case["difficulty"],
                "metrics":    metrics,
                "sources":    result.get("sources", []),
                "chunks_used": result.get("chunks_used", 0),
                "status":     "ok",
            })
        except Exception as e:
            console.print(f"[red]✗ Failed: {case['question'][:50]} — {e}[/red]")
            all_results.append({
                "question":   case["question"][:80],
                "topic":      case["topic"],
                "language":   lang,
                "difficulty": case["difficulty"],
                "status":     f"error: {str(e)[:100]}",
                "metrics":    {"faithfulness":0,"answer_relevance":0,"context_recall":0,"safety":0},
            })

    ok  = [r for r in all_results if r["status"] == "ok"]
    err = [r for r in all_results if r["status"] != "ok"]

    def avg(key): return round(sum(r["metrics"][key] for r in ok)/max(len(ok),1), 3)

    overall = {
        "faithfulness":     avg("faithfulness"),
        "answer_relevance": avg("answer_relevance"),
        "context_recall":   avg("context_recall"),
        "safety":           avg("safety"),
        "total_cases": len(cases), "successful": len(ok), "failed": len(err),
        "vectorstore_chunks": count,
    }

    topics = set(r["topic"] for r in ok)
    by_topic = {}
    for t in topics:
        tr = [r for r in ok if r["topic"] == t]
        by_topic[t] = {k: round(sum(r["metrics"][k] for r in tr)/len(tr),3)
                       for k in ["faithfulness","answer_relevance","context_recall","safety"]}

    _print_table(overall, by_topic, err)

    out = {"timestamp": datetime.now().isoformat(), "overall": overall,
           "by_topic": by_topic, "per_case": all_results}
    path = OUTPUT_DIR / f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    console.print(f"\n[green]✓[/green] Saved → {path}")
    return out


def _print_table(overall, by_topic, errors):
    t = Table(title="RAGAS Evaluation Results", show_header=True, header_style="bold")
    t.add_column("Metric / Topic", style="bold")
    t.add_column("Faithfulness",   justify="center")
    t.add_column("Ans. Relevance", justify="center")
    t.add_column("Context Recall", justify="center")
    t.add_column("Safety",         justify="center")

    def c(v):
        p = v * 100
        col = "green" if p >= 70 else ("yellow" if p >= 40 else "red")
        return f"[{col}]{p:.1f}%[/{col}]"

    t.add_row("🌐 OVERALL",
              c(overall["faithfulness"]), c(overall["answer_relevance"]),
              c(overall["context_recall"]), c(overall["safety"]), style="bold")
    t.add_section()
    for topic, m in by_topic.items():
        t.add_row(f"  ↳ {topic}", c(m["faithfulness"]), c(m["answer_relevance"]),
                  c(m["context_recall"]), c(m["safety"]))

    console.print(t)
    console.print(f"\nTotal: {overall['total_cases']} | ✓ {overall['successful']} passed | ✗ {overall['failed']} failed")
    console.print(f"Vectorstore: {overall['vectorstore_chunks']} chunks indexed")

    if errors:
        console.print(f"\n[red]Các lỗi gặp phải:[/red]")
        for r in errors[:5]:
            console.print(f"  • {r['question'][:60]} → {r['status']}")
        if len(errors) > 5:
            console.print(f"  ... và {len(errors)-5} lỗi khác (xem file JSON)")

    if overall["vectorstore_chunks"] == 0:
        console.print("\n[bold yellow]💡 Để có kết quả tốt hơn:[/bold yellow]")
        console.print("   1. Chạy: python main.py --build")
        console.print("   2. Thêm PDF vào data/raw/guidelines/")
        console.print("   3. Chạy lại: python main.py --eval")
