"""
Unit tests for SRE Action Semantic Equivalence Matching and Risk Detection.
Verifies that OPSRECALL accurately matches action intent across alternative terminologies,
detects harmful conditions, and alerts on historical operational contradictions.
"""

from core.investigation import InvestigationEngine
from core.memory_manager import MemoryManager
from core.validators import RecalledMemoryItem


def test_action_semantic_equivalence_matching():
    """Verify that synonyms and alternative wordings for the same operational intent are recognized as equivalent."""
    # Test HORIZONTAL_SCALE cluster
    is_equiv, cat, conf, explanation = MemoryManager.compare_action_semantics(
        proposed_action="Scale deployment replicas from 4 to 16",
        historical_action="Added more application worker instances to absorb traffic",
    )
    assert is_equiv is True
    assert cat == "HORIZONTAL_SCALE"
    assert conf >= 0.85
    assert "HORIZONTAL_SCALE" in explanation

    # Test CACHE_FLUSH cluster
    is_equiv, cat, conf, _ = MemoryManager.compare_action_semantics(
        proposed_action="Execute redis-cli flushall to purge stale keys",
        historical_action="Cleared entire cache store",
    )
    assert is_equiv is True
    assert cat == "CACHE_FLUSH"

    # Test RETRY_AGGRESSIVE cluster
    is_equiv, cat, conf, _ = MemoryManager.compare_action_semantics(
        proposed_action="Increase max retries to 10 with shorter backoff",
        historical_action="Aggressive retry loops against upstream partner",
    )
    assert is_equiv is True
    assert cat == "RETRY_AGGRESSIVE"


def test_action_distinction_across_different_categories():
    """Verify that distinct operational actions are not conflated."""
    is_equiv, cat, conf, explanation = MemoryManager.compare_action_semantics(
        proposed_action="Increase database max_connections pool size",
        historical_action="Scale pod replicas across Kubernetes cluster",
    )
    assert is_equiv is False
    assert conf >= 0.8
    assert "distinct" in explanation.lower() or "POOL_EXPANSION" in cat


def test_harmful_condition_and_inapplicability_detection():
    """Verify that proposed actions are marked inapplicable when symptoms indicate active harmful conditions."""
    mgr = MemoryManager()
    recalled_mems = [
        RecalledMemoryItem(
            memory_id="MEM-001",
            text="FAILED FIX: Scaled worker replicas to 20 during memory pressure\n=== VERIFIED ROOT CAUSE: Memory leak in worker",
            source_incident_id="INC-011",
        )
    ]

    # Under NodeMemoryPressure, scaling pods exacerbates node degradation
    evals = mgr.evaluate_action_against_history(
        proposed_action="Scale up deployment replicas to 15 pods",
        current_symptoms=["Kubelet reported NodeMemoryPressure", "Pods getting Evicted"],
        current_service="checkout-worker",
        recalled_memories=recalled_mems,
    )

    assert len(evals) >= 1
    eval_item = evals[0]
    assert eval_item.is_equivalent is True
    assert eval_item.action_category == "HORIZONTAL_SCALE"
    assert eval_item.is_applicable_under_current_conditions is False
    assert "Inapplicable" in eval_item.explanation or "NodeMemoryPressure" in eval_item.explanation


def test_contradiction_detection_with_semantic_matching():
    """Verify that detect_contradictions uses semantic clustering to flag dangerous actions."""
    mgr = MemoryManager()
    recalled_mems = [
        RecalledMemoryItem(
            memory_id="MEM-002",
            text="FAILED FIX: Flushed Redis cache\n[HUMAN-VERIFIED ROOT CAUSE]: PostgreSQL query plan regression",
            source_incident_id="INC-004",
        )
    ]

    # Propose purging cache under high database load
    contradictions = mgr.detect_contradictions(
        proposed_action="Run flushdb on Redis cluster to evict corrupted records",
        recalled_memories=recalled_mems,
        current_symptoms=["High QPS traffic", "Database CPU at 98%", "Cache miss spike"],
    )

    assert len(contradictions) >= 1
    assert any("INC-004" in c for c in contradictions)
    assert any("CACHE_FLUSH" in c for c in contradictions)
    assert any("WARNING" in c or "exacerbate" in c for c in contradictions)


def test_investigation_integration_populates_action_evaluations():
    """Verify that InvestigationEngine runs action evaluations and records them in InvestigationResult."""
    engine = InvestigationEngine()
    incident_data = {
        "incident_id": "INC-TEST-SEMANTICS",
        "affected_service": "payment-api",
        "symptoms": ["Cache stampede", "Relational database connection saturation"],
        "error_logs": ["could not obtain connection from pool within 5.0 seconds"],
    }

    result = engine.investigate(incident_data, memory_mode="MEMORY_ENABLED")
    assert result is not None
    assert hasattr(result, "action_evaluations")
    assert isinstance(result.action_evaluations, list)
