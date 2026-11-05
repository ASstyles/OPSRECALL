"""
CLI Evaluation Runner for OPSRECALL.
Executes reproducible benchmarks evaluating incident diagnosis performance
with Hindsight Memory Enabled vs. Memory Disabled.
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
    print("OPSRECALL — OPERATIONAL INCIDENT BENCHMARK EVALUATION")
    print("================================================================================")
    print("Evaluating Top-3 Root Cause Accuracy, Failed Mitigation Avoidance, and Provenance...")
    print("--------------------------------------------------------------------------------")

    eval_fw = get_evaluation_framework()
    results = eval_fw.run_benchmark()

    if "error" in results:
        print(f"[ERROR] {results['error']}")
        return 1

    run_id = results.get("run_id")
    metrics = results.get("metrics", {})
    cases = results.get("cases", [])

    print(f"Run ID: {run_id}")
    print(f"Total Cases Evaluated: {results.get('cases_evaluated')}\n")

    # Table Header
    print(f"{'Case ID':<10} | {'Service':<25} | {'Distractor':<10} | {'Mem OFF':<9} | {'Mem ON':<9} | {'Delta':<7}")
    print("-" * 80)

    for c in cases:
        c_id = c["case_id"]
        svc = c["service"]
        dist = "Yes" if c["is_distractor"] else "No"
        sc_off = c["disabled"]["score"]
        sc_on = c["enabled"]["score"]
        delta = sc_on - sc_off
        delta_str = f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}"
        print(f"{c_id:<10} | {svc:<25} | {dist:<10} | {sc_off:<9.1f} | {sc_on:<9.1f} | {delta_str:<7}")

    print("=" * 80)
    print("MACRO BENCHMARK RESULTS (7 EVALUATION DIMENSIONS):")
    print("--------------------------------------------------------------------------------")
    acc = metrics.get("top_3_root_cause_accuracy", {})
    retrieval = metrics.get("relevant_memory_retrieval_rate", {})
    avoid = metrics.get("failed_mitigation_avoidance_rate", {})
    false_rec = metrics.get("false_historical_recall_rate", {})
    grounding = metrics.get("recommendation_grounding_rate", {})
    uncertainty = metrics.get("appropriate_uncertainty_rate", {})
    composite = metrics.get("composite_score", {})

    print(f"1. Top-3 Root Cause Accuracy:       Memory OFF: {acc.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {acc.get('memory_enabled', 0):>5.1f}%")
    print(f"2. Relevant Memory Retrieval Rate:  Memory OFF: {retrieval.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {retrieval.get('memory_enabled', 0):>5.1f}%")
    print(f"3. Failed Mitigation Avoidance:     Memory OFF: {avoid.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {avoid.get('memory_enabled', 0):>5.1f}%")
    print(f"4. False Recall Rate (Lower=Better):Memory OFF: {false_rec.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {false_rec.get('memory_enabled', 0):>5.1f}%")
    print(f"5. Recommendation Grounding:        Memory OFF: {grounding.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {grounding.get('memory_enabled', 0):>5.1f}%")
    print(f"6. Uncertainty Handling:            Memory OFF: {uncertainty.get('memory_disabled', 0):>5.1f}%  |  Memory ON: {uncertainty.get('memory_enabled', 0):>5.1f}%")
    print(f"7. Overall Composite Score (0-100): Memory OFF: {composite.get('memory_disabled', 0):>5.1f}   |  Memory ON: {composite.get('memory_enabled', 0):>5.1f}")
    print("--------------------------------------------------------------------------------")
    print(f"[SUCCESS] Detailed benchmark reports saved to:")
    print(f"  - outputs/evaluation_results/evaluation_summary.json")
    print(f"  - outputs/evaluation_results/evaluation_case_results.json")
    print(f"  - outputs/evaluation_results/evaluation_{run_id}.json")
    print("================================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())

