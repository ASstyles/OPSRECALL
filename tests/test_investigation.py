"""
Unit tests for Investigation Engine and LLM Reasoning.
"""

import pytest

from core.investigation import InvestigationEngine
from core.validators import InvestigationResult


@pytest.fixture
def checkout_incident():
    return {
        "incident_id": "TEST-CHK-01",
        "incident_title": "Checkout latency post Helm deployment",
        "affected_service": "checkout-api",
        "severity": "SEV-1",
        "symptoms": ["P99 latency surged to 8200ms", "504 Gateway Timeouts on /checkout"],
        "error_logs": ["ERROR checkout.db.pool: Connection checkout timed out after 30000ms"],
        "metrics": {"p99_latency_ms": 8200, "db_wait_queue": 120},
        "deployment_id": "DEP-8492",
        "deployment_or_change": "Helm chart modified max_db_connections",
    }


def test_investigation_memory_disabled(checkout_incident):
    engine = InvestigationEngine()
    result = engine.investigate(checkout_incident, memory_mode="MEMORY_DISABLED")

    assert isinstance(result, InvestigationResult)
    assert result.mode == "MEMORY_DISABLED"
    assert len(result.hypotheses) >= 1
    assert len(result.recommended_remediation_steps) >= 1
    assert result.requires_human_intervention is True
    # Without memory, should have no recalled memories
    assert len(result.recalled_memories) == 0


def test_investigation_memory_enabled(checkout_incident):
    engine = InvestigationEngine()
    result = engine.investigate(checkout_incident, memory_mode="MEMORY_ENABLED")

    assert isinstance(result, InvestigationResult)
    assert result.mode == "MEMORY_ENABLED"
    assert len(result.hypotheses) >= 1

    # Should reference historical precedent or connection pool
    h1 = result.hypotheses[0]
    assert "connection pool" in h1.hypothesis.lower()
    assert result.confidence_level in ["High", "Medium"]
    assert len(result.evidence_summary) > 0


def test_run_comparison_side_by_side(checkout_incident):
    engine = InvestigationEngine()
    disabled, enabled = engine.run_comparison(checkout_incident)

    assert disabled.mode == "MEMORY_DISABLED"
    assert enabled.mode == "MEMORY_ENABLED"
    assert disabled.incident_id == enabled.incident_id

    # Memory enabled should have identified historical context or failed approaches
    assert len(enabled.previous_failed_approaches) >= len(disabled.previous_failed_approaches)
    assert disabled.execution_time_seconds >= 0.0
    assert enabled.execution_time_seconds >= 0.0
