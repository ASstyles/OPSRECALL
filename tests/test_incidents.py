"""
Unit tests for Incident Engine and SQLite persistence.
"""

import tempfile
from pathlib import Path

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


def test_versioned_migrations_applied(temp_db):
    """Verify that all schema versions (1 through 6) are recorded and applied in order."""
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT version, name FROM schema_migrations ORDER BY version ASC")
        rows = cursor.fetchall()
        versions = [r[0] for r in rows]
        assert versions == [1, 2, 3, 4, 5, 6]
        names = [r[1] for r in rows]
        assert "core_tables_v1" in names
        assert "evaluation_16_dimensions_v5" in names
        assert "action_eval_root_cause_match_v6" in names


def test_legacy_schema_upgrade_preserves_records():
    """Verify that running migrations sequentially preserves existing incident records."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Create empty database and run only version 1
    db = DatabaseManager.__new__(DatabaseManager)
    db.db_path = Path(db_path)
    with db.get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        db._migration_v1_core_tables(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (1, 'core_tables_v1', '2026-01-01T00:00:00Z')"
        )
        conn.commit()

        # Insert a record at version 1
        conn.execute(
            """
            INSERT INTO incidents (
                incident_id, incident_title, affected_service, incident_timestamp,
                severity, symptoms, error_logs, metrics
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("INC-LEGACY-01", "Legacy Incident", "auth-svc", "2026-01-01T00:00:00Z", "SEV-2", "[]", "[]", "{}"),
        )
        conn.commit()

    # Now run complete migration pipeline (versions 2 through 5)
    with db.get_connection() as conn:
        db._run_versioned_migrations(conn)

    # Verify that the legacy record is preserved and accessible
    fetched = db.get_incident("INC-LEGACY-01")
    assert fetched is not None
    assert fetched.incident_id == "INC-LEGACY-01"
    assert fetched.incident_title == "Legacy Incident"
    assert fetched.affected_service == "auth-svc"


def test_migration_transaction_rollback_on_failure():
    """Verify that if a migration step fails, the transaction is rolled back and version is not recorded."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db = DatabaseManager(db_path=db_path)

    # Simulate an invalid migration that inserts a row then raises an exception mid-transaction
    def failing_migration(conn):
        conn.execute(
            """
            INSERT INTO incidents (
                incident_id, incident_title, affected_service, incident_timestamp,
                severity, symptoms, error_logs, metrics
            ) VALUES ('INC-TEMP-FAIL', 'Temp Fail', 'svc', '2026-01-01', 'SEV-1', '[]', '[]', '{}')
            """
        )
        conn.execute("INVALID SQL STATEMENT SYNTAX ERROR")

    with db.get_connection() as conn:
        with pytest.raises(RuntimeError) as exc_info:
            migrations = [(7, "failing_migration_v7", failing_migration)]
            for version, name, func in migrations:
                try:
                    with conn:
                        func(conn)
                        conn.execute(
                            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                            (version, name, "2026-01-01"),
                        )
                except Exception as e:
                    raise RuntimeError(f"Database migration {version} ({name}) failed: {e}") from e

        assert "syntax error" in str(exc_info.value).lower()

        # Verify transaction was rolled back (row not present) and version 7 was NOT recorded
        cursor = conn.cursor()
        cursor.execute("SELECT incident_id FROM incidents WHERE incident_id = 'INC-TEMP-FAIL'")
        assert cursor.fetchone() is None

        cursor.execute("SELECT version FROM schema_migrations WHERE version = 7")
        assert cursor.fetchone() is None


def test_export_verified_incidents_json_and_backup(temp_db):
    """Verify verified incident export and online database backup functionality."""
    # Seed 1 unverified and 1 verified incident
    inc_unverified = Incident(
        incident_id="INC-UNVERIFIED-01",
        incident_title="Unverified incident",
        affected_service="api-gw",
        severity="SEV-3",
        symptoms=["Slight latency increase"],
        is_verified=False,
        actual_verified_root_cause=None,
    )
    inc_verified = Incident(
        incident_id="INC-VERIFIED-01",
        incident_title="Verified Incident Resolution",
        affected_service="payment-api",
        severity="SEV-1",
        symptoms=["Checkout 500 spike"],
        is_verified=True,
        actual_verified_root_cause="Stripe webhook secret drift",
        verified_by="Lead SRE",
        resolution="Updated secret in Vault",
    )
    temp_db.upsert_incident(inc_unverified)
    temp_db.upsert_incident(inc_verified)

    with tempfile.TemporaryDirectory() as tmp_dir:
        export_file = Path(tmp_dir) / "verified_export.json"
        exported = temp_db.export_verified_incidents_json(export_path=export_file)

        assert len(exported) >= 1
        exported_ids = [e["incident_id"] for e in exported]
        assert "INC-VERIFIED-01" in exported_ids
        assert "INC-UNVERIFIED-01" not in exported_ids
        assert export_file.exists()

        # Test online backup
        backup_target = Path(tmp_dir) / "test_backup.db"
        res_path = temp_db.backup_database(backup_path=backup_target)
        assert res_path == backup_target
        assert backup_target.exists()
        assert backup_target.stat().st_size > 0

        # Verify backup contains the records
        backup_db = DatabaseManager(db_path=str(backup_target))
        fetched = backup_db.get_incident("INC-VERIFIED-01")
        assert fetched is not None
        assert fetched.verified_by == "Lead SRE"
