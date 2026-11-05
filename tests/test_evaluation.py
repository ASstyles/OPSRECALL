"""
Unit tests for OPSRECALL Evaluation Framework.
"""

from pathlib import Path
import pytest
from core.evaluation import EvaluationFramework
from core.validators import EvaluationCase


def test_load_evaluation_cases():
    eval_fw = EvaluationFramework()
    cases = eval_fw.load_evaluation_cases()
    assert len(cases) >= 5

    # Check first case
    c1 = cases[0]
    assert c1.case_id == "EVAL-001"
    assert c1.affected_service == "checkout-api"
    assert "connection pool" in c1.ground_truth_root_cause.lower()

    # Check distractor case
    distractor_cases = [c for c in cases if c.is_distractor]
    assert len(distractor_cases) >= 1
    assert distractor_cases[0].case_id == "EVAL-006"


def test_benchmark_run_and_scoring():
    eval_fw = EvaluationFramework()
    results = eval_fw.run_benchmark()

    assert "run_id" in results
    assert results["cases_evaluated"] >= 5
    assert "metrics" in results

    metrics = results["metrics"]
    assert "accuracy" in metrics
    assert "failed_fix_avoidance" in metrics
    assert "average_score" in metrics

    # Memory ON average score should be >= Memory OFF
    avg_on = metrics["average_score"]["memory_enabled"]
    avg_off = metrics["average_score"]["memory_disabled"]
    assert avg_on >= avg_off

    # Check output file was generated
    run_id = results["run_id"]
    out_file = Path("outputs/evaluation_results") / f"evaluation_{run_id}.json"
    assert out_file.exists()

