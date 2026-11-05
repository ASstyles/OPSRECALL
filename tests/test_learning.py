"""
Unit tests for Learning Engine and resolution retention.
"""

from unittest.mock import MagicMock
import pytest
from core.learning_engine import LearningEngine
from core.memory_manager import MemoryManager
from database.db import DatabaseManager


def test_confirm_and_retain_resolution():
    mock_mm = MagicMock()
    mock_mm.retain_incident.return_value = {
        "success": True,
        "mode": "LIVE_HINDSIGHT",
        "operation_id": "op-test-999",
        "document_id": "INC-001",
    }

    engine = LearningEngine(memory_manager=mock_mm)

    res = engine.confirm_and_retain_resolution(
        incident_id="INC-001",
        verified_root_cause="Database pool max connections capped at 10",
        successful_resolution="Restored max_db_connections to 150",
        failed_approaches=["Increasing timeouts", "Scaling pods"],
        verification_evidence="P99 latency stabilized at 110ms",
        lessons_learned="Always check pool sizing before touching timeouts",
        verified_by="Lead SRE",
    )

    assert res["success"] is True
    assert res["incident_id"] == "INC-001"
    assert res["retained_to_hindsight"] is True
    assert res["hindsight_operation_id"] == "op-test-999"

    # Verify history retrieval
    history = engine.get_learning_history(limit=5)
    assert len(history) >= 1
    latest = history[0]
    assert latest["incident_id"] == "INC-001"
    assert "Increasing timeouts" in latest["failed_approaches"]


def test_confirm_resolution_validation_errors():
    engine = LearningEngine()
    with pytest.raises(ValueError, match="Incident ID cannot be empty"):
        engine.confirm_and_retain_resolution(
            incident_id="",
            verified_root_cause="cause",
            successful_resolution="fix",
            failed_approaches=[],
            verification_evidence="",
            lessons_learned="",
        )

    with pytest.raises(ValueError, match="Verified root cause"):
        engine.confirm_and_retain_resolution(
            incident_id="INC-001",
            verified_root_cause="",
            successful_resolution="fix",
            failed_approaches=[],
            verification_evidence="",
            lessons_learned="",
        )

