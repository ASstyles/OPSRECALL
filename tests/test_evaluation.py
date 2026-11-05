"""
Unit tests for OPSRECALL Evaluation Framework and Ground-Truth Isolation.
"""

from pathlib import Path
import pytest
from core.evaluation import EvaluationFramework
from core.validators import EvaluationCase, EvaluationGroundTruth


def test_load_evaluation_cases_isolated():
    eval_fw = EvaluationFramework()
    cases = eval_fw.load_evaluation_cases()
    assert len(cases) == 12, f"Expected 12 benchmark cases, found {len(cases)}"

    # Check that model-facing cases contain ZERO ground-truth answer keys
    for case in cases:
        case_dict = case.model_dump()
        assert "ground_truth_root_cause" not in case_dict
        assert "expected_historical_match" not in case_dict
        assert "unsuccessful_mitigations_to_avoid" not in case_dict
        assert "is_distractor" not in case_dict
        assert len(case.symptoms) > 0


def test_load_ground_truth_isolated():
    eval_fw = EvaluationFramework()
    gt_map = eval_fw.load_ground_truth()
    assert len(gt_map) == 12

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


def test_benchmark_run_and_7_metrics():
    eval_fw = EvaluationFramework()
    results = eval_fw.run_benchmark()

    assert "run_id" in results
    assert results["cases_evaluated"] == 12
    assert "metrics" in results

    metrics = results["metrics"]
    assert "top_3_root_cause_accuracy" in metrics
    assert "relevant_memory_retrieval_rate" in metrics
    assert "failed_mitigation_avoidance_rate" in metrics
    assert "false_historical_recall_rate" in metrics
    assert "recommendation_grounding_rate" in metrics
    assert "appropriate_uncertainty_rate" in metrics
    assert "composite_score" in metrics

    # Memory ON composite score should be >= Memory OFF
    avg_on = metrics["composite_score"]["memory_enabled"]
    avg_off = metrics["composite_score"]["memory_disabled"]
    assert avg_on >= avg_off

    # Check canonical output files generated
    assert (Path("outputs/evaluation_results") / "evaluation_summary.json").exists()
    assert (Path("outputs/evaluation_results") / "evaluation_case_results.json").exists()
    assert (Path("outputs/evaluation_results") / f"evaluation_{results['run_id']}.json").exists()
