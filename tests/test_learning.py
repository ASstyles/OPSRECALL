"""
Unit tests for Learning Engine, resolution retention, multi-stage statuses, and conflict detection.
"""

from unittest.mock import MagicMock
import pytest
from core.learning_engine import LearningEngine
from core.memory_manager import MemoryManager
from database.db import DatabaseManager


def test_confirm_and_retain_resolution_live_mocked():
    mock_mm = MagicMock()
    mock_mm.client.is_configured = True
    mock_mm.client.wait_for_document_processing.return_value = True
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
    assert res["status"] == "MEMORY_RETRIEVABLE"

    # Verify history retrieval
    history = engine.get_learning_history(limit=5)
    assert len(history) >= 1
    latest = history[0]
    assert latest["incident_id"] == "INC-001"
    assert "Increasing timeouts" in latest["failed_approaches"]


def test_confirm_resolution_unconfigured_local_fallback():
    mock_mm = MagicMock()
    mock_mm.client.is_configured = False

    engine = LearningEngine(memory_manager=mock_mm)

    res = engine.confirm_and_retain_resolution(
        incident_id="INC-002",
        verified_root_cause="Worker concurrency reduced to 2",
        successful_resolution="Restored HPA concurrency to 8",
        failed_approaches=["Purged DLQ"],
        verification_evidence="Queue backlog drained",
        lessons_learned="Do not touch concurrency during migrations",
        verified_by="Incident Commander",
    )

    assert res["success"] is True
    assert res["retained_to_hindsight"] is False
    assert res["status"] == "LOCAL_AUDIT_SAVED"
    assert "Offline Preview Mode" in res["message"]


def test_conflict_detection_on_root_cause_update():
    """Verify that contradictory feedback on an existing incident is detected and logged."""
    mock_mm = MagicMock()
    mock_mm.client.is_configured = False

    engine = LearningEngine(memory_manager=mock_mm)

    # Initial confirmation
    engine.confirm_and_retain_resolution(
        incident_id="INC-TEST-CONFLICT",
        verified_root_cause="Original Cause A: Network interface reset",
        successful_resolution="Restarted switch",
        failed_approaches=[],
        verification_evidence="Interface link up",
        lessons_learned="",
        verified_by="Engineer Alice",
    )

    # Conflicting update with different root cause
    res2 = engine.confirm_and_retain_resolution(
        incident_id="INC-TEST-CONFLICT",
        verified_root_cause="Contradicting Cause B: Database Deadlock",
        successful_resolution="Killed blocking query",
        failed_approaches=[],
        verification_evidence="Lock cleared",
        lessons_learned="",
        verified_by="Engineer Bob",
    )

    assert res2["conflict_detected"] is True
    assert "Conflicting root cause update" in res2["conflict_details"]
    assert "Engineer Bob" in res2["conflict_details"]


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
