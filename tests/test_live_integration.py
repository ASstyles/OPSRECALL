"""
Opt-in live integration tests for OPSRECALL.
Requires live HINDSIGHT_API_KEY and GROQ_API_KEY in environment or .env.
Automatically skipped if external credentials are not present.
"""

import pytest
from config import settings
from core.hindsight_client import get_hindsight_client
from core.llm_engine import get_llm_engine
from core.memory_manager import get_memory_manager


@pytest.mark.skipif(
    not settings.is_hindsight_configured(),
    reason="Live Hindsight credentials not configured in environment.",
)
def test_live_hindsight_health_and_bank():
    client = get_hindsight_client()
    health = client.check_health()
    assert health["status"] == "CONNECTED"
    assert health["mode"] == "LIVE"
    assert health["bank_exists"] is True


@pytest.mark.skipif(
    not settings.is_hindsight_configured(),
    reason="Live Hindsight credentials not configured in environment.",
)
def test_live_hindsight_recall():
    mm = get_memory_manager()
    results = mm.recall_memories("checkout-api latency 504 gateway timeout")
    # Should execute successfully without throwing exceptions
    assert isinstance(results, list)


@pytest.mark.skipif(
    not settings.is_groq_configured(),
    reason="Live Groq credentials not configured in environment.",
)
def test_live_groq_generation():
    llm = get_llm_engine()
    test_incident = {
        "incident_id": "TEST-LIVE",
        "affected_service": "checkout-api",
        "severity": "SEV-1",
        "symptoms": ["P99 latency high"],
        "error_logs": ["DB pool timeout"],
    }
    result = llm.generate_investigation(test_incident, recalled_memories=[], memory_mode="MEMORY_DISABLED")
    assert "hypotheses" in result
    assert len(result["hypotheses"]) >= 1
    assert "groq:" in result.get("llm_model", "")

