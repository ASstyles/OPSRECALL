"""
Unit tests for Hindsight Client wrapper and Memory Manager.
"""

from unittest.mock import MagicMock, patch
import pytest
from core.hindsight_client import HindsightClientWrapper
from core.memory_manager import MemoryManager
from core.validators import Incident, RecalledMemoryItem
from hindsight_client_api.exceptions import ApiException, UnauthorizedException


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
        actual_verified_root_cause="Database connection pool misconfiguration",
        failed_mitigation_attempts=[
            "Increased checkout-api HTTP client timeout from 5s to 15s. FAILED: Exacerbated thread starvation",
        ],
        successful_mitigation="Restored max_db_connections to 150",
    )


def test_memory_formatting(sample_incident):
    mm = MemoryManager()
    formatted = mm.format_incident_for_retention(sample_incident)

    assert "=== INCIDENT RECORD: INC-001 ===" in formatted
    assert "Service: checkout-api" in formatted
    assert "FAILED MITIGATION ATTEMPTS (DO NOT REPEAT):" in formatted
    assert "Increased checkout-api HTTP client timeout" in formatted
    assert "Restored max_db_connections to 150" in formatted


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
    # Should handle gracefully and return empty list rather than crashing
    memories = mm.recall_memories("test query")
    assert memories == []

