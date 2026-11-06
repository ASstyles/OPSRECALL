"""
Unit tests for OPSRECALL data models and validators.
"""

import pytest
from pydantic import ValidationError

from core.validators import (
    EvaluationCase,
    EvaluationGroundTruth,
    FailedApproachWarning,
    Hypothesis,
    Incident,
    ResolutionFeedback,
)


def test_valid_incident_creation():
    incident = Incident(
        incident_id="INC-999",
        incident_title="Test Outage",
        affected_service="test-service",
        severity="SEV-1",
        symptoms=["API unresponsive", "500 errors"],
        error_logs=["NullPointer at main.py:42"],
        metrics={"latency_ms": 5000},
    )
    assert incident.incident_id == "INC-999"
    assert incident.severity == "SEV-1"
    assert incident.data_type == "SIMULATED_INCIDENT"
    assert len(incident.symptoms) == 2


def test_invalid_severity():
    with pytest.raises(ValidationError):
        Incident(
            incident_id="INC-999",
            incident_title="Bad Sev",
            affected_service="svc",
            severity="SEV-99",  # Invalid
        )


def test_evaluation_case_creation():
    case = EvaluationCase(
        case_id="EVAL-100",
        case_title="Test Evaluation",
        affected_service="auth-svc",
        severity="SEV-2",
        symptoms=["Login timeout"],
    )
    assert case.case_id == "EVAL-100"
    assert case.affected_service == "auth-svc"


def test_evaluation_ground_truth_creation():
    gt = EvaluationGroundTruth(
        case_id="EVAL-100",
        scenario_type="recurrent_incident",
        ground_truth_root_cause="Redis memory exhaustion",
        unsuccessful_mitigations_to_avoid=["Restarting auth service"],
        is_distractor=False,
    )
    assert gt.case_id == "EVAL-100"
    assert not gt.is_distractor
    assert "Redis" in gt.ground_truth_root_cause


def test_hypothesis_model():
    h = Hypothesis(
        rank=1,
        hypothesis="Database connection pool starvation",
        supporting_evidence=["Active: 10/10", "Waiters: 50"],
        likelihood="High",
        historical_precedent="INC-001",
    )
    assert h.rank == 1
    assert h.likelihood == "High"
    assert h.historical_precedent == "INC-001"


def test_failed_approach_warning():
    fa = FailedApproachWarning(
        approach="Increased timeouts",
        why_failed="Worsened pool starvation",
        historical_source_incident="INC-001",
    )
    assert fa.approach == "Increased timeouts"
    assert fa.historical_source_incident == "INC-001"


def test_resolution_feedback_model():
    fb = ResolutionFeedback(
        incident_id="INC-001",
        verified_root_cause="Connection pool max connections misconfigured",
        successful_resolution="Restored pool size to 150",
        failed_approaches=["Scaling pods"],
        verification_evidence="Latency stabilized at 115ms",
        lessons_learned="Always check pool size before timeouts",
    )
    assert fb.incident_id == "INC-001"
    assert not fb.retained_to_hindsight
