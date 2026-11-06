"""
Unit tests for Hindsight Client wrapper and Memory Manager.
Validates structured formatting, multi-factor ranking, structured retrievals,
duplicate prevention, contradiction detection, and API exception handling.
"""

from unittest.mock import MagicMock

import pytest
from hindsight_client_api.exceptions import ApiException

from core.hindsight_client import HindsightClientWrapper
from core.memory_manager import MemoryManager
from core.validators import Incident, RecalledMemoryItem


@pytest.fixture
def sample_incident():
    return Incident(
        incident_id="INC-001",
        incident_title="Checkout API Latency Spike Post-Deployment",
        affected_service="checkout-api",
        severity="SEV-1",
        symptoms=["P99 latency surged from 120ms to 8500ms"],
        error_logs=["ERROR checkout.db.pool: Connection checkout timed out after 30000ms"],
        metrics={"p99_latency_ms": 8500},
        deployment_id="DEP-8492",
        deployment_or_change="Helm values max_db_connections lowered to 10",
        suspected_cause="Suspected network saturation",
        actual_verified_root_cause="Database connection pool misconfiguration",
        is_verified=True,
        verified_by="Lead SRE Alice",
        failed_mitigation_attempts=[
            "Increased checkout-api HTTP client timeout from 5s to 15s. FAILED: Exacerbated thread starvation",
        ],
        successful_mitigation="Restored max_db_connections to 150",
    )


def test_memory_formatting_and_segregation(sample_incident):
    mm = MemoryManager()
    formatted = mm.format_incident_for_retention(sample_incident)

    assert "=== INCIDENT RECORD: INC-001 ===" in formatted
    assert "Service: checkout-api" in formatted
    assert "FAILED MITIGATION ATTEMPTS (DO NOT REPEAT):" in formatted
    assert "Increased checkout-api HTTP client timeout" in formatted
    assert "Restored max_db_connections to 150" in formatted

    # Crucial Principle: Strict segregation between suspected and verified cause
    assert "[UNVERIFIED INITIAL SUSPICION]: Suspected network saturation" in formatted
    assert "[HUMAN-VERIFIED ROOT CAUSE]: Database connection pool misconfiguration" in formatted
    assert "Verified By: Lead SRE Alice" in formatted


def test_query_construction():
    mm = MemoryManager()
    query = mm.build_recall_query(
        service="payment-gateway",
        symptoms=["502 Bad Gateway", "High error rate"],
        error_logs=["SSL handshake alert 45"],
        deployment_change="No recent deploy",
    )
    assert "Service: payment-gateway" in query
    assert "502 Bad Gateway" in query
    assert "SSL handshake" in query


def test_failed_approaches_extraction():
    mm = MemoryManager()
    memories = [
        RecalledMemoryItem(
            memory_id="mem-1",
            text="FAILED FIX: Scaled pod replicas from 4 to 12. FAILED: Worsened DB connection queue backlog.",
            source_incident_id="INC-001",
        ),
        RecalledMemoryItem(
            memory_id="mem-2",
            text="Healthy pod deployment and regular cron execution.",
            source_incident_id="INC-002",
        ),
    ]
    warnings = mm.extract_failed_approaches(memories)
    assert len(warnings) >= 1
    assert "Scaled pod replicas" in warnings[0].approach
    assert warnings[0].historical_source_incident == "INC-001"


def test_contradiction_detection():
    mm = MemoryManager()
    memories = [
        RecalledMemoryItem(
            memory_id="mem-1",
            text="FAILED FIX: Executing redis-cli flushall during high traffic. FAILED: Caused primary database collapse.",
            source_incident_id="INC-004",
        )
    ]
    contradictions = mm.detect_contradictions("Executing redis-cli flushall to clear keys", memories)
    assert len(contradictions) >= 1
    assert "INC-004" in contradictions[0]
    assert "flushall" in contradictions[0]


def test_duplicate_retention_idempotency(sample_incident):
    mm = MemoryManager()
    # First retention in unconfigured mode
    res1 = mm.retain_incident(sample_incident)
    assert res1["success"] is False  # unconfigured

    # Second retention with exact same content hash
    res2 = mm.retain_incident(sample_incident)
    assert res2["mode"] == "IDEMPOTENT_SKIPPED"
    assert res2["success"] is True


def test_rank_and_structure_retrievals():
    mm = MemoryManager()
    memories = [
        RecalledMemoryItem(
            memory_id="mem-1",
            text=(
                "Title: Connection pool exhaustion post Helm deploy\n"
                "Service: checkout-api\n"
                "[HUMAN-VERIFIED ROOT CAUSE]: max_db_connections set too low\n"
                "FAILED FIX: Increasing timeouts worsened thread starvation\n"
                "- Permanent Fix: Restored max_db_connections to 150"
            ),
            source_incident_id="INC-001",
            is_verified=True,
            metadata={"service": "checkout-api"},
        ),
        RecalledMemoryItem(
            memory_id="mem-2",
            text="Title: General network latency\nService: other-service\nRoot cause: Unrelated",
            source_incident_id="INC-999",
            is_verified=False,
            metadata={"service": "other-service"},
        ),
    ]

    structured = mm.rank_and_structure_retrievals(
        recalled_memories=memories,
        current_service="checkout-api",
        current_symptoms=["Connection acquisition timeout", "P99 latency surged"],
        current_errors=["Connection checkout timed out waiting for pool connection"],
        current_change="max_connections modified",
    )

    assert len(structured) == 2
    # INC-001 should rank first due to service context, error signature, and verified status
    assert structured[0].incident_id == "INC-001"
    assert structured[0].relevance_score > structured[1].relevance_score
    assert "Aligned failure signature: connection pool" in structured[0].matching_evidence
    assert structured[0].is_verified is True
    assert len(structured[0].failed_mitigations_to_avoid) >= 1


def test_hindsight_health_check_unconfigured():
    client = HindsightClientWrapper(api_key="")
    health = client.check_health()
    assert health["status"] == "NOT_CONFIGURED"
    assert health["mode"] == "UNCONFIGURED"
    assert not health["bank_exists"]


def test_hindsight_mocked_retain_success(sample_incident):
    mock_sdk_client = MagicMock()
    mock_sdk_client.retain.return_value = MagicMock(
        success=True,
        bank_id="opsrecall-demo",
        items_count=1,
        operation_id="op-12345",
    )

    client_wrapper = HindsightClientWrapper(api_key="valid-test-key")
    client_wrapper._client = mock_sdk_client

    mm = MemoryManager(client=client_wrapper)
    result = mm.retain_incident(sample_incident)

    assert result["success"] is True
    assert result["mode"] == "LIVE_HINDSIGHT"
    assert result["document_id"] == "INC-001"
    mock_sdk_client.retain.assert_called_once()


def test_hindsight_mocked_recall_success():
    mock_sdk_client = MagicMock()
    mock_result_item = MagicMock(
        id="mem-99",
        text="Incident INC-003: Downstream TLS certificate expired on payment-vault",
        type="experience",
        document_id="INC-003",
        tags=["payment-gateway", "sev-1"],
        metadata={"incident_id": "INC-003"},
        mentioned_at="2026-10-24T03:04:00Z",
        scores=MagicMock(relevance=0.95),
    )
    mock_sdk_client.recall.return_value = MagicMock(results=[mock_result_item])

    client_wrapper = HindsightClientWrapper(api_key="valid-test-key")
    client_wrapper._client = mock_sdk_client

    mm = MemoryManager(client=client_wrapper)
    memories = mm.recall_memories("payment-gateway 502 error")

    assert len(memories) == 1
    assert memories[0].source_incident_id == "INC-003"
    assert memories[0].relevance_score == 0.95


def test_hindsight_api_exception_handling():
    mock_sdk_client = MagicMock()
    mock_sdk_client.recall.side_effect = ApiException(status=500, reason="Internal Server Error")

    client_wrapper = HindsightClientWrapper(api_key="valid-test-key")
    client_wrapper._client = mock_sdk_client

    mm = MemoryManager(client=client_wrapper)
    memories = mm.recall_memories("test query")
    assert memories == []
