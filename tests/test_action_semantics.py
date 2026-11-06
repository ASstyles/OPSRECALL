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


def test_negation_awareness_opposing_polarity():
    """Verify that negated action proposals are classified as NEGATED_ACTION and never marked equivalent."""
    eval_result = MemoryManager.compare_action_semantics(
        proposed_action="Do not scale checkout workers",
        historical_action="Scale checkout workers from 4 to 16",
    )
    assert eval_result.semantic_relation == "NEGATED_ACTION"
    assert eval_result.is_equivalent is False
    assert "action_polarity" in eval_result.conflicting_fields
    assert "opposing operational polarities" in eval_result.explanation


def test_direction_of_change_opposite():
    """Verify that opposite directional operations (e.g. increase vs decrease) are distinguished."""
    eval_retries = MemoryManager.compare_action_semantics(
        proposed_action="Increase max retries to 10 with shorter backoff",
        historical_action="Reduce retries to 2 and enforce backoff",
    )
    assert eval_retries.semantic_relation == "OPPOSITE_ACTION"
    assert eval_retries.is_equivalent is False
    assert "direction_of_change" in eval_retries.conflicting_fields

    eval_scale = MemoryManager.compare_action_semantics(
        proposed_action="Scale up worker pods to 20",
        historical_action="Scale down pods to 2",
    )
    assert eval_scale.semantic_relation == "OPPOSITE_ACTION"
    assert eval_scale.is_equivalent is False
    assert "direction_of_change" in eval_scale.conflicting_fields


def test_architectural_layer_distinction():
    """Verify that actions targeting different architectural layers are recognized as distinct."""
    eval_layer = MemoryManager.compare_action_semantics(
        proposed_action="Rollout restart application pod instances",
        historical_action="Restart PostgreSQL database server",
    )
    assert eval_layer.semantic_relation == "RELATED_BUT_DISTINCT"
    assert eval_layer.is_equivalent is False
    assert "resource_type" in eval_layer.conflicting_fields
    assert "distinct architectural layers" in eval_layer.explanation


def test_action_intent_normalization_properties():
    """Verify that normalize_action_intent correctly extracts structured fields and risk properties."""
    intent_scale = MemoryManager.normalize_action_intent(
        "Scale checkout workers from 4 to 16", service="checkout-service"
    )
    assert intent_scale.action_polarity == "POSITIVE"
    assert intent_scale.direction_of_change == "INCREASE"
    assert intent_scale.resource_type == "POD"
    assert intent_scale.operation_category == "HORIZONTAL_SCALE"
    assert intent_scale.target_service == "checkout-service"
    assert intent_scale.requires_human_approval is False

    intent_flush = MemoryManager.normalize_action_intent("Execute redis-cli flushall to clear keys")
    assert intent_flush.direction_of_change == "PURGE"
    assert intent_flush.resource_type == "CACHE"
    assert intent_flush.operation_category == "CACHE_FLUSH"
    assert intent_flush.requires_human_approval is True
    assert intent_flush.potential_blast_radius == "HIGH"


def test_historical_successful_resolution_not_flagged_as_failed_mitigation():
    """Verify that verified successful fixes in historical memories are not falsely flagged as failed mitigations."""
    mgr = MemoryManager()
    recalled_mems = [
        RecalledMemoryItem(
            memory_id="MEM-003",
            text=(
                "=== INCIDENT RECORD: INC-005 ===\n"
                "Service: worker-service\n"
                "FAILED MITIGATION ATTEMPTS (DO NOT REPEAT):\n"
                "- FAILED FIX: Purged Redis cache during high query volume\n"
                "VERIFIED EFFECTIVE RESOLUTION:\n"
                "- Permanent Fix: Scaled worker replicas from 4 to 16\n"
                "[HUMAN-VERIFIED ROOT CAUSE]: Worker thread pool starvation"
            ),
            source_incident_id="INC-005",
            is_verified=True,
        )
    ]

    # 1. Propose scaling workers (which was the successful permanent fix)
    evals_scale = mgr.evaluate_action_against_history(
        proposed_action="Scale worker replicas from 4 to 16",
        current_symptoms=["Task queue backlog increasing"],
        current_service="worker-service",
        recalled_memories=recalled_mems,
    )
    # Scaling worker replicas was NOT a failed fix; it was the effective resolution!
    # Therefore, no failed fix warning should be raised, but the successful match should be recognized.
    assert not any(e.historical_outcome == "FAILED" for e in evals_scale)
    assert any(e.historical_outcome == "SUCCESSFUL" for e in evals_scale)

    # 2. Propose purging Redis cache (which was the failed fix)
    evals_flush = mgr.evaluate_action_against_history(
        proposed_action="Run redis-cli flushall to clear queue cache",
        current_symptoms=["Task queue backlog increasing"],
        current_service="worker-service",
        recalled_memories=recalled_mems,
    )
    assert len(evals_flush) >= 1
    assert evals_flush[0].is_equivalent is True
    assert evals_flush[0].action_category == "CACHE_FLUSH"
