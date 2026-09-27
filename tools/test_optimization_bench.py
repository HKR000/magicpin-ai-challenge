"""Benchmark script to inspect composer output and validator decisions across all 25 triggers."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vera.orchestrator import Vera
from judge_simulator import DatasetLoader, CanonicalRubricProvider, LLMScorer, DATASET_DIR

def run_bench():
    vera = Vera()
    loader = DatasetLoader(DATASET_DIR)
    loader.load()
    scorer = LLMScorer(CanonicalRubricProvider(), loader)

    # Ingest categories
    for slug, cat in loader.categories.items():
        vera.context_engine.ingest("category", slug, 1, cat, "2026-04-26T08:00:00Z", "bench")
    # Ingest merchants
    for mid, m in loader.merchants.items():
        vera.context_engine.ingest("merchant", mid, 1, m, "2026-04-26T08:00:00Z", "bench")
    # Ingest customers
    for cid, c in loader.customers.items():
        vera.context_engine.ingest("customer", cid, 1, c, "2026-04-26T08:00:00Z", "bench")
    # Ingest triggers
    for tid, t in loader.triggers.items():
        vera.context_engine.ingest("trigger", tid, 1, t, "2026-04-26T08:00:00Z", "bench")

    results = []
    for tid in sorted(loader.triggers.keys()):
        composed, decision, err = vera.handle_proactive_trigger(tid, conversation_id=f"bench_{tid}")
        trigger = loader.triggers.get(tid, {})
        mid = trigger.get("merchant_id") or "m_001_drmeera_dentist_delhi"
        merchant = loader.merchants.get(mid, {})
        cid = trigger.get("customer_id")
        customer = loader.customers.get(cid) if cid else None
        category = loader.categories.get(merchant.get("category_slug", ""), {})

        action_dict = {
            "trigger_id": tid,
            "merchant_id": mid,
            "customer_id": cid,
            "body": composed.body if composed else "",
            "cta": composed.cta.value if composed else "binary"
        }
        score = scorer.score(action_dict, category, merchant, trigger, customer)
        results.append({
            "tid": tid,
            "body": composed.body if composed else "",
            "cta": composed.cta.value if composed else "",
            "scores": {
                "spec": score.specificity,
                "cat": score.category_fit,
                "mer": score.merchant_fit,
                "dec": score.decision_quality,
                "eng": score.engagement_compulsion,
                "total": score.total
            },
            "reasons": {
                "spec": score.specificity_reason,
                "cat": score.category_fit_reason,
                "mer": score.merchant_fit_reason,
                "dec": score.decision_quality_reason,
                "eng": score.engagement_reason
            }
        })

    n = len(results)
    avg_total = sum(r["scores"]["total"] for r in results) / n
    avg_spec = sum(r["scores"]["spec"] for r in results) / n
    avg_cat = sum(r["scores"]["cat"] for r in results) / n
    avg_mer = sum(r["scores"]["mer"] for r in results) / n
    avg_dec = sum(r["scores"]["dec"] for r in results) / n
    avg_eng = sum(r["scores"]["eng"] for r in results) / n

    print(f"Evaluated {n} triggers:")
    print(f"  Avg Specificity: {avg_spec:.2f}/10")
    print(f"  Avg Category:    {avg_cat:.2f}/10")
    print(f"  Avg Merchant:    {avg_mer:.2f}/10")
    print(f"  Avg Decision:    {avg_dec:.2f}/10")
    print(f"  Avg Engagement:  {avg_eng:.2f}/10")
    print(f"  TOTAL AVERAGE:   {avg_total:.2f}/50 ({(avg_total/50.0)*100:.2f}%)")

    for r in results:
        print(f"\n[{r['tid']}] Total: {r['scores']['total']}/50 | Spec: {r['scores']['spec']} Cat: {r['scores']['cat']} Mer: {r['scores']['mer']} Dec: {r['scores']['dec']} Eng: {r['scores']['eng']}")
        print("  Body:", r["body"])
        print("  Reasons:", r["reasons"])

if __name__ == "__main__":
    run_bench()
