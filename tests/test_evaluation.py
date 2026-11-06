"""
Unit tests for OPSRECALL Evaluation Framework and Ground-Truth Isolation.
Validates 16 benchmark cases, anti-leakage isolation, and 12-dimensional scoring.
"""

from pathlib import Path

from core.evaluation import EvaluationFramework


def test_load_evaluation_cases_isolated():
    eval_fw = EvaluationFramework()
    cases = eval_fw.load_evaluation_cases()
    assert len(cases) == 16, f"Expected 16 benchmark cases, found {len(cases)}"

    # Check that model-facing cases contain ZERO ground-truth answer keys
    for case in cases:
        case_dict = case.model_dump()
        assert "ground_truth_root_cause" not in case_dict
        assert "expected_historical_match" not in case_dict
        assert "unsuccessful_mitigations_to_avoid" not in case_dict
        assert "is_distractor" not in case_dict
        assert "expected_optimal_first_action" not in case_dict
        assert len(case.symptoms) > 0


def test_load_ground_truth_isolated():
    eval_fw = EvaluationFramework()
    gt_map = eval_fw.load_ground_truth()
    assert len(gt_map) == 16

    # Check recurrent case EVAL-001
    gt1 = gt_map.get("EVAL-001")
    assert gt1 is not None
    assert "connection pool" in gt1.ground_truth_root_cause.lower()
    assert gt1.expected_historical_match == "INC-001"
    assert len(gt1.unsuccessful_mitigations_to_avoid) >= 1

    # Check distractor case EVAL-006
    gt6 = gt_map.get("EVAL-006")
    assert gt6 is not None
    assert gt6.is_distractor is True
    assert gt6.expected_historical_match is None

    # Check novel distractor EVAL-012
    gt12 = gt_map.get("EVAL-012")
    assert gt12 is not None
    assert gt12.requires_uncertainty is True


def test_benchmark_run_and_16_metrics():
    eval_fw = EvaluationFramework()
    results = eval_fw.run_benchmark()

    assert "run_id" in results
    assert results["cases_evaluated"] == 16
    assert "metrics" in results

    metrics = results["metrics"]
    assert "top_1_root_cause_accuracy" in metrics
    assert "top_3_root_cause_accuracy" in metrics
    assert "causal_reasoning_quality" in metrics
    assert "evidence_grounding_rate" in metrics
    assert "retrieval_precision_pct" in metrics
    assert "retrieval_recall_pct" in metrics
    assert "mean_reciprocal_rank" in metrics
    assert "relevant_memory_retrieval_rate" in metrics
    assert "failed_mitigation_avoidance_rate" in metrics
    assert "recommendation_action_quality" in metrics
    assert "recommendation_safety_rate" in metrics
    assert "false_historical_recall_rate" in metrics
    assert "novel_incident_handling_rate" in metrics
    assert "brier_score" in metrics
    assert "expected_calibration_error" in metrics
    assert "investigation_consistency_rate" in metrics
    assert "human_verification_compliance_rate" in metrics
    assert "composite_score" in metrics

    # Verify calibration details
    assert "calibration_details" in results
    assert "bins_memory_enabled" in results["calibration_details"]
    assert len(results["calibration_details"]["bins_memory_enabled"]) == 3

    # Memory ON composite score should be >= Memory OFF
    avg_on = metrics["composite_score"]["memory_enabled"]
    avg_off = metrics["composite_score"]["memory_disabled"]
    assert avg_on >= avg_off

    # Check canonical output files generated
    assert (Path("outputs/evaluation_results") / "evaluation_summary.json").exists()
    assert (Path("outputs/evaluation_results") / "evaluation_case_results.json").exists()
    assert (Path("outputs/evaluation_results") / f"evaluation_{results['run_id']}.json").exists()
