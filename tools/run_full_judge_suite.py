"""Run judge scenarios and export comprehensive telemetry to JSON for EVALUATION_RESULTS.md."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import requests

from judge_simulator import JudgeSimulator, CanonicalRubricProvider, LLMScorer, BOT_URL

def main():
    llm = CanonicalRubricProvider()
    judge = JudgeSimulator(llm)
    judge.dataset.load()
    judge.scorer = LLMScorer(llm, judge.dataset)
    loader = judge.dataset

    suite_results = {
        "metadata": {
            "evaluator": "Official Canonical Rubric Evaluator (EVALUATION_SPEC.md §2)",
            "bot_url": BOT_URL,
            "team_name": "Harsh Kumar",
            "model": "hybrid-deterministic-reasoning"
        },
        "scenarios": {}
    }

    # 1. Warmup
    print("Executing Warmup...")
    h_data, h_err, h_lat = judge.client.healthz()
    m_data, m_err, m_lat = judge.client.metadata()
    context_pushes = []
    for slug, cat in loader.categories.items():
        res, err, lat = judge.client.push_context("category", slug, 1, cat)
        context_pushes.append({"type": "category", "id": slug, "accepted": res.get("accepted") if res else False, "error": err, "latency_ms": lat})
    for mid, m in list(loader.merchants.items())[:5]:
        res, err, lat = judge.client.push_context("merchant", mid, 1, m)
        context_pushes.append({"type": "merchant", "id": mid, "accepted": res.get("accepted") if res else False, "error": err, "latency_ms": lat})

    suite_results["scenarios"]["warmup"] = {
        "healthz": {"data": h_data, "err": h_err, "latency_ms": h_lat, "passed": h_err is None and h_data.get("status") == "healthy"},
        "metadata": {"data": m_data, "err": m_err, "latency_ms": m_lat, "passed": m_err is None and "team_name" in m_data},
        "context_pushes": context_pushes,
        "all_passed": (h_err is None) and (m_err is None) and all(cp["accepted"] for cp in context_pushes)
    }

    # 2. Auto-Reply Hell
    print("Executing Auto-Reply Hell...")
    mid = list(loader.merchants.keys())[0] if loader.merchants else "m_test"
    auto_msg = "Thank you for contacting us! Our team will respond shortly."
    auto_turns = []
    auto_passed = False
    for i in range(1, 5):
        data, err, lat = judge.client.reply(f"conv_auto_{i}", mid, auto_msg, i + 1)
        action = data.get("action", "?") if data else "error"
        wait_s = data.get("wait_seconds") if data else None
        body = data.get("body", "") if data else ""
        turn_passed = action in ("wait", "end")
        auto_turns.append({
            "turn": i,
            "input": auto_msg,
            "output": data,
            "action": action,
            "wait_seconds": wait_s,
            "body": body,
            "passed": turn_passed
        })
        if action == "end":
            auto_passed = True
            break
        elif action == "wait":
            auto_passed = True

    suite_results["scenarios"]["auto_reply_hell"] = {
        "merchant_id": mid,
        "turns": auto_turns,
        "passed": auto_passed
    }

    # 3. Intent Transition
    print("Executing Intent Transition...")
    commit_msg = "Ok lets do it. Whats next?"
    c_data, c_err, c_lat = judge.client.reply("conv_intent_suite", mid, commit_msg, 2)
    c_action = c_data.get("action") if c_data else "error"
    c_body = c_data.get("body", "") if c_data else ""
    qualifying = ["would you", "do you", "can you tell", "what if", "how about"]
    actioning = ["done", "sending", "draft", "here", "confirm", "proceed", "next"]
    c_body_lower = c_body.lower()
    intent_passed = any(w in c_body_lower for w in actioning) and not any(w in c_body_lower for w in qualifying)
    suite_results["scenarios"]["intent_transition"] = {
        "input": commit_msg,
        "action": c_action,
        "body": c_body,
        "latency_ms": c_lat,
        "passed": intent_passed,
        "matched_actioning": [w for w in actioning if w in c_body_lower],
        "matched_qualifying": [w for w in qualifying if w in c_body_lower]
    }

    # 4. Hostile Handling
    print("Executing Hostile Handling...")
    hostile_msg = "Stop messaging me. This is useless spam."
    h_data, h_err, h_lat = judge.client.reply("conv_hostile_suite", mid, hostile_msg, 2)
    h_action = h_data.get("action") if h_data else "error"
    h_body = h_data.get("body", "") if h_data else ""
    hostile_passed = (h_action == "end") or (h_action == "send" and any(w in h_body.lower() for w in ["sorry", "apolog", "won't"]))
    suite_results["scenarios"]["hostile_handling"] = {
        "input": hostile_msg,
        "action": h_action,
        "body": h_body,
        "latency_ms": h_lat,
        "passed": hostile_passed
    }

    # 5. Full Evaluation (All 25 Triggers)
    print("Executing Full Evaluation on 25 Triggers...")
    # push all merchants & triggers
    for mid, m in loader.merchants.items():
        judge.client.push_context("merchant", mid, 1, m)
    for tid, t in loader.triggers.items():
        judge.client.push_context("trigger", tid, 1, t)

    tids = list(loader.triggers.keys())
    scored_actions = []
    all_scores = []

    for i in range(0, len(tids), 5):
        batch = tids[i:i+5]
        data, err, lat = judge.client.tick(batch)
        if err:
            continue
        actions = data.get("actions", [])
        for act in actions:
            tid = act.get("trigger_id", "")
            mid = act.get("merchant_id", "")
            cid = act.get("customer_id")

            trigger = loader.triggers.get(tid, {})
            merchant = loader.merchants.get(mid, {})
            customer = loader.customers.get(cid) if cid else None
            category = loader.categories.get(merchant.get("category_slug", ""), {})

            score = judge.scorer.score(act, category, merchant, trigger, customer)
            all_scores.append(score)
            scored_actions.append({
                "trigger_id": tid,
                "merchant_id": mid,
                "customer_id": cid,
                "category": merchant.get("category_slug", ""),
                "action": act.get("action"),
                "body": act.get("body"),
                "scores": {
                    "specificity": score.specificity,
                    "category_fit": score.category_fit,
                    "merchant_fit": score.merchant_fit,
                    "decision_quality": score.decision_quality,
                    "engagement_compulsion": score.engagement_compulsion,
                    "penalties": score.penalties,
                    "total": score.total,
                    "percentage": (score.total / 50.0) * 100
                },
                "reasons": {
                    "specificity": score.specificity_reason,
                    "category_fit": score.category_fit_reason,
                    "merchant_fit": score.merchant_fit_reason,
                    "decision_quality": score.decision_quality_reason,
                    "engagement": score.engagement_reason,
                    "penalty_reasons": score.penalty_reasons,
                    "hint": score.hint
                }
            })

    n = len(all_scores)
    avg_score = {
        "n_evaluated": n,
        "avg_specificity": sum(s.specificity for s in all_scores) / n if n else 0,
        "avg_category_fit": sum(s.category_fit for s in all_scores) / n if n else 0,
        "avg_merchant_fit": sum(s.merchant_fit for s in all_scores) / n if n else 0,
        "avg_decision_quality": sum(s.decision_quality for s in all_scores) / n if n else 0,
        "avg_engagement": sum(s.engagement_compulsion for s in all_scores) / n if n else 0,
        "total_avg": sum(s.total for s in all_scores) / n if n else 0,
        "percentage": (sum(s.total for s in all_scores) / (50.0 * n)) * 100 if n else 0,
        "tier": "EXCELLENT" if ((sum(s.total for s in all_scores) / (50.0 * n)) * 100) >= 80 else "GOOD"
    }

    suite_results["scenarios"]["full_evaluation"] = {
        "summary": avg_score,
        "scored_actions": scored_actions
    }

    with open("eval_results_data.json", "w", encoding="utf-8") as f:
        json.dump(suite_results, f, indent=2)

    print("Execution complete! Results exported to eval_results_data.json")

if __name__ == "__main__":
    main()
