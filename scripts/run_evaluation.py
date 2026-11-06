"""
CLI Evaluation Runner for OPSRECALL.
Executes reproducible benchmarks evaluating incident diagnosis performance
with Hindsight Memory Enabled vs. Memory Disabled across 16 scenarios and 16 evaluation dimensions.
Usage:
    python scripts/run_evaluation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.evaluation import get_evaluation_framework


def main() -> int:
    print("================================================================================")
    print("OPSRECALL -- 16-DIMENSIONAL INCIDENT BENCHMARK EVALUATION")
    print("================================================================================")
    print("Evaluating Root Cause Accuracy, Retrieval Quality, Safety, Calibration & Consistency...")
    print("--------------------------------------------------------------------------------")

    eval_fw = get_evaluation_framework()
    results = eval_fw.run_benchmark()

    if "error" in results:
        print(f"[ERROR] {results['error']}")
        return 1

    run_id = results.get("run_id")
    metrics = results.get("metrics", {})
    cases = results.get("cases", [])
    hindsight_status = results.get("hindsight_status", "UNKNOWN")

    print(f"Run ID:            {run_id}")
    print(f"Hindsight Status:  {hindsight_status}")
    print(f"Total Scenarios:   {results.get('cases_evaluated')}\n")

    # Table Header
    print(f"{'Case ID':<9} | {'Service':<25} | {'Category':<18} | {'Mem OFF':<8} | {'Mem ON':<8} | {'Delta':<7}")
    print("-" * 88)

    for c in cases:
        c_id = c["case_id"]
        svc = c["service"]
        cat = c.get("domain_category", "general")[:18]
        sc_off = c["disabled"]["score"]
        sc_on = c["enabled"]["score"]
        delta = sc_on - sc_off
        delta_str = f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}"
        print(f"{c_id:<9} | {svc:<25} | {cat:<18} | {sc_off:<8.1f} | {sc_on:<8.1f} | {delta_str:<7}")

    print("=" * 88)
    print("MACRO BENCHMARK RESULTS (16 INDEPENDENT EVALUATION DIMENSIONS):")
    print("--------------------------------------------------------------------------------")
    top1 = metrics.get("top_1_root_cause_accuracy", {})
    top3 = metrics.get("top_3_root_cause_accuracy", {})
    causal = metrics.get("causal_reasoning_quality", {})
    grounding = metrics.get("evidence_grounding_rate", {})
    prec = metrics.get("retrieval_precision_pct", {})
    recall = metrics.get("retrieval_recall_pct", {})
    mrr = metrics.get("mean_reciprocal_rank", {})
    retrieval = metrics.get("relevant_memory_retrieval_rate", {})
    avoid = metrics.get("failed_mitigation_avoidance_rate", {})
    action_q = metrics.get("recommendation_action_quality", {})
    safety = metrics.get("recommendation_safety_rate", {})
    false_rec = metrics.get("false_historical_recall_rate", {})
    novel = metrics.get("novel_incident_handling_rate", {})
    brier = metrics.get("brier_score", {})
    ece = metrics.get("expected_calibration_error", {})
    consistency = metrics.get("investigation_consistency_rate", {})
    human = metrics.get("human_verification_compliance_rate", {})
    composite = metrics.get("composite_score", {})

    print(f" 1. Top-1 Root Cause Accuracy:       Memory OFF: {top1.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {top1.get('memory_enabled', 0):>5.1f}%")
    print(f" 2. Top-3 Root Cause Accuracy:       Memory OFF: {top3.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {top3.get('memory_enabled', 0):>5.1f}%")
    print(f" 3. Causal Reasoning Quality:        Memory OFF: {causal.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {causal.get('memory_enabled', 0):>5.1f}%")
    print(f" 4. Evidence Grounding Rate:         Memory OFF: {grounding.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {grounding.get('memory_enabled', 0):>5.1f}%")
    print(f" 5. Retrieval Precision@k:           Memory OFF: {prec.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {prec.get('memory_enabled', 0):>5.1f}%")
    print(f" 6. Retrieval Recall@k:              Memory OFF: {recall.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {recall.get('memory_enabled', 0):>5.1f}%")
    print(f" 7. Mean Reciprocal Rank (MRR):      Memory OFF: {mrr.get('memory_disabled', 0):>5.3f}   |  Memory ON: {mrr.get('memory_enabled', 0):>5.3f}")
    print(f" 8. Relevant Memory Retrieval Rate:  Memory OFF: {retrieval.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {retrieval.get('memory_enabled', 0):>5.1f}%")
    print(f" 9. Failed Mitigation Avoidance:     Memory OFF: {avoid.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {avoid.get('memory_enabled', 0):>5.1f}%")
    print(f"10. Recommendation Action Quality:   Memory OFF: {action_q.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {action_q.get('memory_enabled', 0):>5.1f}%")
    print(f"11. Recommendation Safety Rate:      Memory OFF: {safety.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {safety.get('memory_enabled', 0):>5.1f}%")
    print(f"12. False Recall Rate (Lower=Better):Memory OFF: {false_rec.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {false_rec.get('memory_enabled', 0):>5.1f}%")
    print(f"13. Novel Incident Handling Rate:    Memory OFF: {novel.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {novel.get('memory_enabled', 0):>5.1f}%")
    print(f"14. Confidence Calibration:          Memory OFF: Brier={brier.get('memory_disabled', 0):.3f}, ECE={ece.get('memory_disabled', 0):.3f}")
    print(f"                                     Memory ON:  Brier={brier.get('memory_enabled', 0):.3f}, ECE={ece.get('memory_enabled', 0):.3f}")
    print(f"15. Investigation Consistency Rate:  Memory OFF: {consistency.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {consistency.get('memory_enabled', 0):>5.1f}%")
    print(f"16. Human Verification Compliance:   Memory OFF: {human.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {human.get('memory_enabled', 0):>5.1f}%")
    print("--------------------------------------------------------------------------------")
    print(f"COMPOSITE NORMALIZED SCORE (0-100):  Memory OFF: {composite.get('memory_disabled', 0):>5.1f}   |  Memory ON: {composite.get('memory_enabled', 0):>5.1f}")
    print("--------------------------------------------------------------------------------")
    print(f"[SUCCESS] Detailed benchmark reports saved to:")
    print(f"  - outputs/evaluation_results/evaluation_summary.json")
    print(f"  - outputs/evaluation_results/evaluation_case_results.json")
    print(f"  - outputs/evaluation_results/evaluation_{run_id}.json")
    print("================================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
