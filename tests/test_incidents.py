"""
Unit tests for Incident Engine and SQLite persistence.
"""

import tempfile
import pytest
from core.incident_engine import IncidentEngine
from core.validators import Incident
from database.db import DatabaseManager


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = DatabaseManager(db_path=db_path)
    return db


def test_incident_engine_loads_data(temp_db):
    engine = IncidentEngine()
    incidents = engine.get_all_incidents()
    assert len(incidents) >= 5

    inc_001 = engine.get_incident("INC-001")
    assert inc_001 is not None
    assert inc_001.affected_service == "checkout-api"
    assert "Database connection pool misconfiguration" in inc_001.actual_verified_root_cause


def test_sqlite_upsert_and_fetch(temp_db):
    custom_inc = Incident(
        incident_id="INC-CUSTOM-01",
        incident_title="Memory leak in Worker",
        affected_service="worker-svc",
        severity="SEV-2",
        symptoms=["Sawtooth RAM graph"],
        error_logs=["OOMKilled exit code 137"],
        metrics={"memory_mb": 4096},
        actual_verified_root_cause="Unbounded cache growth",
    )
    temp_db.upsert_incident(custom_inc)

    fetched = temp_db.get_incident("INC-CUSTOM-01")
    assert fetched is not None
    assert fetched.incident_title == "Memory leak in Worker"
    assert fetched.actual_verified_root_cause == "Unbounded cache growth"


def test_service_health_summary(temp_db):
    engine = IncidentEngine()
    summary = engine.get_service_health_summary()
    assert len(summary) > 0

    services = [s["service_name"] for s in summary]
    assert "checkout-api" in services

