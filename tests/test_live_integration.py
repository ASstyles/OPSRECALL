"""
Opt-in live integration tests for OPSRECALL.
Requires live HINDSIGHT_API_KEY and GROQ_API_KEY in environment or .env.
Target test bank: `opsrecall-live-tests` (isolated from primary demo bank).
Automatically and transparently skipped if external credentials are not present.
"""

import uuid

import pytest

from config import settings
from core.hindsight_client import HindsightClientWrapper, get_hindsight_client
from core.llm_engine import get_llm_engine


@pytest.mark.skipif(
    not settings.is_hindsight_configured(),
    reason="Live Hindsight credentials (HINDSIGHT_API_KEY) not configured in environment.",
)
def test_live_hindsight_health_and_test_bank():
    client = get_hindsight_client()
    health = client.check_health()
    assert health["status"] == "CONNECTED"
    assert health["mode"] == "LIVE"
    assert health["bank_exists"] is True

    # Verify or create test bank
    test_bank = settings.HINDSIGHT_TEST_BANK_ID
    assert client.ensure_bank_exists(bank_id=test_bank) is True


@pytest.mark.skipif(
    not settings.is_hindsight_configured(),
    reason="Live Hindsight credentials (HINDSIGHT_API_KEY) not configured in environment.",
)
def test_live_hindsight_retain_recall_and_persistence():
    client = get_hindsight_client()
    test_bank = settings.HINDSIGHT_TEST_BANK_ID
    client.ensure_bank_exists(bank_id=test_bank)

    run_token = uuid.uuid4().hex[:6].upper()
    doc_id = f"TEST-INC-PYTEST-{run_token}"
    content = (
        f"Pytest live memory test incident on live-test-svc: connection pool timeout on checkout DB. "
        f"Unique verification probe token: {run_token}."
    )

    # 1. Retain
    resp = client.retain(
        content=content,
        document_id=doc_id,
        metadata={"run_token": run_token},
        tags=["pytest-live", "live-test-svc"],
        bank_id=test_bank,
    )
    assert getattr(resp, "success", False) is True

    # 2. Bounded Polling
    indexed = client.wait_for_document_processing(
        document_id=doc_id,
        bank_id=test_bank,
        timeout_seconds=20.0,
        poll_interval=1.5,
    )
    assert indexed is True, f"Document {doc_id} was not indexed within bounded timeout."

    # 3. Recall in Fresh Session (WITHOUT leaking probe token or doc_id into query)
    fresh_client = HindsightClientWrapper(
        base_url=client.base_url,
        api_key=client.api_key,
        bank_id=test_bank,
    )
    recall_resp = fresh_client.recall(
        query="live-test-svc connection pool timeout on checkout DB",
        bank_id=test_bank,
    )
    results = getattr(recall_resp, "results", [])
    assert isinstance(results, list) and len(results) > 0, (
        f"Live Hindsight recall must return non-empty results for retained probe incident {doc_id}."
    )

    # Assert exact probe document ID or unique token is recovered from recalled content
    found = any(doc_id in getattr(r, "document_id", "") or run_token in getattr(r, "text", "") for r in results)
    assert found, (
        f"Retained probe document {doc_id} or unique token {run_token} was not found in recall results: {results}"
    )

    # 4. Negative Control Query (Rejection of Unrelated Incidents)
    negative_resp = fresh_client.recall(
        query="unrelated astrophysical supernova cosmic background radiation query",
        bank_id=test_bank,
    )
    neg_results = getattr(negative_resp, "results", [])
    neg_found = any(doc_id in getattr(r, "document_id", "") or run_token in getattr(r, "text", "") for r in neg_results)
    assert not neg_found, f"Probe document {doc_id} leaked into unrelated negative control query results!"


@pytest.mark.skipif(
    not settings.is_groq_configured(),
    reason="Live Groq credentials (GROQ_API_KEY) not configured in environment.",
)
def test_live_groq_generation_structured_json():
    llm = get_llm_engine()
    test_incident = {
        "incident_id": "TEST-LIVE-PYTEST",
        "affected_service": "checkout-api",
        "severity": "SEV-1",
        "symptoms": ["P99 latency high", "504 timeouts"],
        "error_logs": ["DB pool timeout after 30000ms"],
        "metrics": {"p99_latency_ms": 7500},
    }
    result = llm.generate_investigation(
        test_incident,
        recalled_memories=[],
        memory_mode="MEMORY_DISABLED",
    )
    assert "hypotheses" in result
    assert len(result["hypotheses"]) >= 1
    assert "recommended_remediation_steps" in result
    assert "groq:" in result.get("llm_model", "")
