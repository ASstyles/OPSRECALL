"""
SQLite database manager for OPSRECALL local state persistence.
Stores local incident cache, audit logs of investigations, human-verified resolutions,
and benchmark experiment records.
NOTE: SQLite acts as an audit log / local record-keeper and NEVER substitutes for Hindsight memory.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from config import settings
from core.validators import CaseEvaluationScore, Incident, InvestigationResult, ResolutionFeedback


class DatabaseManager:
    """Manages SQLite connection and schemas for OPSRECALL local audit records."""

    def __init__(self, db_path: str | None = None):
        self.db_path = Path(db_path or settings.SQLITE_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Create, configure, and yield a SQLite connection with guaranteed cleanup."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Initialize database schema via versioned transactional migrations."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
            self._run_versioned_migrations(conn)

    def _run_versioned_migrations(self, conn: sqlite3.Connection) -> None:
        """Execute pending versioned migrations in order with transactional rollback safety."""
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_migrations")
        applied_versions = {row[0] for row in cursor.fetchall()}

        migrations = [
            (1, "core_tables_v1", self._migration_v1_core_tables),
            (2, "incident_verification_v2", self._migration_v2_incident_verification),
            (3, "investigation_structured_v3", self._migration_v3_investigation_structured),
            (4, "resolution_multistage_v4", self._migration_v4_resolution_multistage),
            (5, "evaluation_16_dimensions_v5", self._migration_v5_evaluation_16d),
            (6, "action_eval_root_cause_match_v6", self._migration_v6_action_eval_root_cause_match),
        ]

        for version, name, func in migrations:
            if version not in applied_versions:
                try:
                    with conn:
                        func(conn)
                        from datetime import datetime, timezone

                        now_str = datetime.now(timezone.utc).isoformat()
                        conn.execute(
                            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                            (version, name, now_str),
                        )
                except Exception as e:
                    import logging

                    logging.getLogger("opsrecall.db").error(f"Migration {version} ({name}) failed: {e}")
                    raise RuntimeError(f"Database migration {version} ({name}) failed: {e}") from e

    def _migration_v1_core_tables(self, conn: sqlite3.Connection) -> None:
        """Version 1: Create core initial audit tables."""
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                incident_title TEXT NOT NULL,
                affected_service TEXT NOT NULL,
                incident_timestamp TEXT NOT NULL,
                severity TEXT NOT NULL,
                symptoms TEXT NOT NULL,
                error_logs TEXT NOT NULL,
                metrics TEXT NOT NULL,
                deployment_id TEXT,
                deployment_or_change TEXT,
                suspected_cause TEXT,
                actual_verified_root_cause TEXT,
                is_verified INTEGER DEFAULT 0,
                verified_by TEXT,
                verified_at TEXT,
                diagnostic_actions_attempted TEXT,
                failed_mitigation_attempts TEXT,
                successful_mitigation TEXT,
                resolution TEXT,
                resolution_outcome TEXT,
                verification_evidence TEXT,
                lessons_learned TEXT,
                content_hash TEXT,
                data_type TEXT DEFAULT 'SIMULATED_INCIDENT',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS investigations (
                investigation_id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                retrieval_mode_label TEXT DEFAULT 'DISABLED',
                executive_summary TEXT,
                hypotheses TEXT NOT NULL,
                recalled_memories TEXT,
                structured_retrievals TEXT,
                historical_incidents_referenced TEXT,
                previous_failed_approaches TEXT,
                memory_contradictions_detected TEXT,
                recommended_remediation_steps TEXT,
                confidence_level TEXT,
                llm_model TEXT,
                execution_time_seconds REAL,
                created_at TEXT NOT NULL,
                raw_result TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS resolutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                verified_root_cause TEXT NOT NULL,
                successful_resolution TEXT NOT NULL,
                failed_approaches TEXT NOT NULL,
                verification_evidence TEXT,
                lessons_learned TEXT,
                verified_by TEXT,
                status TEXT DEFAULT 'FEEDBACK_RECEIVED',
                retained_to_hindsight INTEGER DEFAULT 0,
                hindsight_operation_id TEXT,
                error_message TEXT,
                conflict_detected INTEGER DEFAULT 0,
                conflict_details TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluation_runs (
                run_id TEXT PRIMARY KEY,
                run_timestamp TEXT NOT NULL,
                cases_evaluated INTEGER NOT NULL,
                accuracy_enabled REAL NOT NULL,
                accuracy_disabled REAL NOT NULL,
                avoidance_enabled REAL NOT NULL,
                avoidance_disabled REAL NOT NULL,
                avg_score_enabled REAL NOT NULL,
                avg_score_disabled REAL NOT NULL,
                summary_json TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluation_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                memory_mode TEXT NOT NULL,
                top_1_root_cause_hit INTEGER DEFAULT 0,
                top_3_root_cause_hit INTEGER NOT NULL,
                retrieved_expected_historical INTEGER NOT NULL,
                recalled_failed_mitigations INTEGER NOT NULL,
                avoided_unsuccessful_mitigations INTEGER NOT NULL,
                false_recall_flagged INTEGER NOT NULL,
                appropriate_uncertainty INTEGER NOT NULL,
                is_safe_recommendation INTEGER DEFAULT 1,
                overall_score REAL NOT NULL,
                explanation TEXT,
                FOREIGN KEY (run_id) REFERENCES evaluation_runs (run_id)
            )
            """
        )

    def _migration_v2_incident_verification(self, conn: sqlite3.Connection) -> None:
        """Version 2: Add verification and content hash columns to incidents."""
        self._migrate_table(
            conn,
            "incidents",
            [
                ("is_verified", "INTEGER DEFAULT 0"),
                ("verified_by", "TEXT"),
                ("verified_at", "TEXT"),
                ("content_hash", "TEXT"),
            ],
        )

    def _migration_v3_investigation_structured(self, conn: sqlite3.Connection) -> None:
        """Version 3: Add structured retrieval and contradiction tracking to investigations."""
        self._migrate_table(
            conn,
            "investigations",
            [
                ("retrieval_mode_label", "TEXT DEFAULT 'DISABLED'"),
                ("structured_retrievals", "TEXT"),
                ("previous_failed_approaches", "TEXT"),
                ("memory_contradictions_detected", "TEXT"),
            ],
        )

    def _migration_v4_resolution_multistage(self, conn: sqlite3.Connection) -> None:
        """Version 4: Add 5-stage feedback lifecycle and conflict columns to resolutions."""
        self._migrate_table(
            conn,
            "resolutions",
            [
                ("status", "TEXT DEFAULT 'FEEDBACK_RECEIVED'"),
                ("error_message", "TEXT"),
                ("conflict_detected", "INTEGER DEFAULT 0"),
                ("conflict_details", "TEXT"),
            ],
        )

    def _migration_v5_evaluation_16d(self, conn: sqlite3.Connection) -> None:
        """Version 5: Add 16-dimensional benchmark columns to evaluation_details."""
        self._migrate_table(
            conn,
            "evaluation_details",
            [
                ("top_1_root_cause_hit", "INTEGER DEFAULT 0"),
                ("is_safe_recommendation", "INTEGER DEFAULT 1"),
                ("causal_reasoning_score", "REAL DEFAULT 0.0"),
                ("evidence_grounding_score", "REAL DEFAULT 0.0"),
                ("retrieval_precision", "REAL DEFAULT 0.0"),
                ("retrieval_recall", "REAL DEFAULT 0.0"),
                ("reciprocal_rank", "REAL DEFAULT 0.0"),
                ("action_quality_score", "REAL DEFAULT 0.0"),
                ("confidence_calibration_error", "REAL DEFAULT 0.0"),
                ("brier_score", "REAL DEFAULT 0.0"),
            ],
        )

    def _migration_v6_action_eval_root_cause_match(self, conn: sqlite3.Connection) -> None:
        """Version 6: Add action evaluations to investigations and root cause match type to evaluation_details."""
        self._migrate_table(
            conn,
            "investigations",
            [
                ("action_evaluations", "TEXT"),
            ],
        )
        self._migrate_table(
            conn,
            "evaluation_details",
            [
                ("root_cause_match_type", "TEXT DEFAULT 'UNSUPPORTED'"),
            ],
        )

    def _migrate_table(self, conn: sqlite3.Connection, table_name: str, columns: list[tuple[str, str]]) -> None:
        """Add missing columns to an existing SQLite table if not present."""
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        for col_name, col_type in columns:
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass
        conn.commit()

    def upsert_incident(self, incident: Incident) -> None:
        """Insert or replace an incident record in local database."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO incidents (
                    incident_id, incident_title, affected_service, incident_timestamp,
                    severity, symptoms, error_logs, metrics, deployment_id,
                    deployment_or_change, suspected_cause, actual_verified_root_cause,
                    is_verified, verified_by, verified_at,
                    diagnostic_actions_attempted, failed_mitigation_attempts,
                    successful_mitigation, resolution, resolution_outcome,
                    verification_evidence, lessons_learned, content_hash, data_type, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    incident.incident_id,
                    incident.incident_title,
                    incident.affected_service,
                    incident.incident_timestamp,
                    incident.severity,
                    json.dumps(incident.symptoms),
                    json.dumps(incident.error_logs),
                    json.dumps(incident.metrics),
                    incident.deployment_id,
                    incident.deployment_or_change,
                    incident.suspected_cause,
                    incident.actual_verified_root_cause,
                    1 if incident.is_verified or incident.actual_verified_root_cause else 0,
                    incident.verified_by,
                    incident.verified_at,
                    json.dumps(incident.diagnostic_actions_attempted),
                    json.dumps(incident.failed_mitigation_attempts),
                    incident.successful_mitigation,
                    incident.resolution,
                    incident.resolution_outcome,
                    incident.verification_evidence,
                    incident.lessons_learned,
                    incident.content_hash or incident.compute_content_hash(),
                    incident.data_type,
                ),
            )
            conn.commit()

    def get_incident(self, incident_id: str) -> Incident | None:
        """Fetch an incident by its ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM incidents WHERE incident_id = ?", (incident_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_incident(row)

    def list_incidents(self) -> list[Incident]:
        """Return all stored incidents."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM incidents ORDER BY incident_id ASC")
            return [self._row_to_incident(row) for row in cursor.fetchall()]

    def count_incidents(self) -> int:
        """Count total incidents stored."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM incidents")
            return cursor.fetchone()[0]

    def save_investigation(self, result: InvestigationResult) -> None:
        """Save an investigation report to the audit table."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO investigations (
                    investigation_id, incident_id, mode, retrieval_mode_label, executive_summary,
                    hypotheses, recalled_memories, structured_retrievals, historical_incidents_referenced,
                    previous_failed_approaches, memory_contradictions_detected, action_evaluations,
                    recommended_remediation_steps, confidence_level, llm_model, execution_time_seconds,
                    created_at, raw_result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.investigation_id,
                    result.incident_id,
                    result.mode,
                    result.retrieval_mode_label,
                    result.executive_summary,
                    json.dumps([h.model_dump() for h in result.hypotheses]),
                    json.dumps([m.model_dump() for m in result.recalled_memories]),
                    json.dumps([s.model_dump() for s in result.structured_retrievals]),
                    json.dumps(result.historical_incidents_referenced),
                    json.dumps([f.model_dump() for f in result.previous_failed_approaches]),
                    json.dumps(result.memory_contradictions_detected),
                    json.dumps([a.model_dump() for a in getattr(result, "action_evaluations", [])]),
                    json.dumps([r.model_dump() for r in result.recommended_remediation_steps]),
                    result.confidence_level,
                    result.llm_model,
                    result.execution_time_seconds,
                    result.created_at,
                    result.model_dump_json(),
                ),
            )
            conn.commit()

    def list_investigations(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent investigations."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT investigation_id, incident_id, mode, retrieval_mode_label, executive_summary,
                       confidence_level, llm_model, execution_time_seconds, created_at
                FROM investigations
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def save_resolution(self, feedback: ResolutionFeedback) -> int:
        """Save a human-confirmed incident resolution with multi-stage status and conflict tracking."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO resolutions (
                    incident_id, verified_root_cause, successful_resolution,
                    failed_approaches, verification_evidence, lessons_learned,
                    verified_by, status, retained_to_hindsight, hindsight_operation_id,
                    error_message, conflict_detected, conflict_details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback.incident_id,
                    feedback.verified_root_cause,
                    feedback.successful_resolution,
                    json.dumps(feedback.failed_approaches),
                    feedback.verification_evidence,
                    feedback.lessons_learned,
                    feedback.verified_by,
                    feedback.status,
                    1 if feedback.retained_to_hindsight else 0,
                    feedback.hindsight_operation_id,
                    feedback.error_message,
                    1 if feedback.conflict_detected else 0,
                    feedback.conflict_details,
                    feedback.created_at,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def list_resolutions(self, limit: int = 20) -> list[dict[str, Any]]:
        """List human verified resolutions."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM resolutions ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            )
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                d["failed_approaches"] = json.loads(d["failed_approaches"])
                results.append(d)
            return results

    def save_evaluation_run(
        self,
        run_id: str,
        run_timestamp: str,
        cases_evaluated: int,
        accuracy_enabled: float,
        accuracy_disabled: float,
        avoidance_enabled: float,
        avoidance_disabled: float,
        avg_score_enabled: float,
        avg_score_disabled: float,
        summary_json: dict[str, Any],
        details: list[CaseEvaluationScore],
    ) -> None:
        """Persist an evaluation run and its detailed case scores."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evaluation_runs (
                    run_id, run_timestamp, cases_evaluated,
                    accuracy_enabled, accuracy_disabled,
                    avoidance_enabled, avoidance_disabled,
                    avg_score_enabled, avg_score_disabled, summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    run_timestamp,
                    cases_evaluated,
                    accuracy_enabled,
                    accuracy_disabled,
                    avoidance_enabled,
                    avoidance_disabled,
                    avg_score_enabled,
                    avg_score_disabled,
                    json.dumps(summary_json),
                ),
            )

            for d in details:
                conn.execute(
                    """
                    INSERT INTO evaluation_details (
                        run_id, case_id, memory_mode, top_1_root_cause_hit, top_3_root_cause_hit,
                        root_cause_match_type,
                        retrieved_expected_historical, recalled_failed_mitigations,
                        avoided_unsuccessful_mitigations, false_recall_flagged,
                        appropriate_uncertainty, is_safe_recommendation,
                        causal_reasoning_score, evidence_grounding_score,
                        retrieval_precision, retrieval_recall, reciprocal_rank,
                        action_quality_score, confidence_calibration_error, brier_score,
                        overall_score, explanation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        d.case_id,
                        d.memory_mode,
                        1 if getattr(d, "top_1_root_cause_hit", False) else 0,
                        1 if d.top_3_root_cause_hit else 0,
                        getattr(d, "root_cause_match_type", "UNSUPPORTED"),
                        1 if d.retrieved_expected_historical else 0,
                        1 if d.recalled_failed_mitigations else 0,
                        1 if d.avoided_unsuccessful_mitigations else 0,
                        1 if d.false_recall_flagged else 0,
                        1 if d.appropriate_uncertainty else 0,
                        1 if getattr(d, "is_safe_recommendation", True) else 0,
                        getattr(d, "causal_reasoning_score", 0.0),
                        getattr(d, "evidence_grounding_score", 0.0),
                        d.retrieval_precision if d.retrieval_precision is not None else 0.0,
                        d.retrieval_recall if d.retrieval_recall is not None else 0.0,
                        d.reciprocal_rank if d.reciprocal_rank is not None else 0.0,
                        getattr(d, "action_quality_score", 0.0),
                        getattr(d, "confidence_calibration_error", 0.0),
                        getattr(d, "brier_score", 0.0),
                        d.overall_score,
                        d.explanation,
                    ),
                )
            conn.commit()

    def get_latest_evaluation_run(self) -> dict[str, Any] | None:
        """Fetch the most recent evaluation benchmark summary."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM evaluation_runs ORDER BY run_timestamp DESC LIMIT 1
                """
            )
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["summary_json"] = json.loads(res["summary_json"])
            return res

    def _row_to_incident(self, row: sqlite3.Row) -> Incident:
        """Convert a SQLite row into an Incident Pydantic object."""
        return Incident(
            incident_id=row["incident_id"],
            incident_title=row["incident_title"],
            affected_service=row["affected_service"],
            incident_timestamp=row["incident_timestamp"],
            severity=row["severity"],
            symptoms=json.loads(row["symptoms"] or "[]"),
            error_logs=json.loads(row["error_logs"] or "[]"),
            metrics=json.loads(row["metrics"] or "{}"),
            deployment_id=row["deployment_id"],
            deployment_or_change=row["deployment_or_change"],
            suspected_cause=row["suspected_cause"],
            actual_verified_root_cause=row["actual_verified_root_cause"],
            is_verified=bool(row["is_verified"])
            if "is_verified" in row.keys()
            else bool(row["actual_verified_root_cause"]),
            verified_by=row["verified_by"] if "verified_by" in row.keys() else None,
            verified_at=row["verified_at"] if "verified_at" in row.keys() else None,
            diagnostic_actions_attempted=json.loads(row["diagnostic_actions_attempted"] or "[]"),
            failed_mitigation_attempts=json.loads(row["failed_mitigation_attempts"] or "[]"),
            successful_mitigation=row["successful_mitigation"],
            resolution=row["resolution"],
            resolution_outcome=row["resolution_outcome"],
            verification_evidence=row["verification_evidence"],
            lessons_learned=row["lessons_learned"],
            content_hash=row["content_hash"] if "content_hash" in row.keys() else None,
            data_type=row["data_type"] if "data_type" in row.keys() else "INCIDENT_POSTMORTEM",
        )

    def export_verified_incidents_json(self, export_path: str | Path | None = None) -> list[dict[str, Any]]:
        """
        Export all human-verified incidents to structured JSON format.
        Preserves complete provenance, reviewer identity, and verified resolutions.
        """
        verified_incidents = [
            inc
            for inc in self.list_incidents()
            if inc.is_verified
            or (inc.actual_verified_root_cause is not None and len(inc.actual_verified_root_cause) > 0)
        ]
        records = [inc.model_dump() for inc in verified_incidents]
        if export_path:
            p = Path(export_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
        return records

    def backup_database(self, backup_path: str | Path | None = None) -> Path:
        """
        Create a consistent online SQLite backup safely copying the live database.
        """
        from datetime import datetime, timezone

        if backup_path is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            target_path = self.db_path.parent / f"backup_opsrecall_{timestamp}.db"
        else:
            target_path = Path(backup_path)

        target_path.parent.mkdir(parents=True, exist_ok=True)

        with self.get_connection() as src_conn:
            dest_conn = sqlite3.connect(str(target_path))
            try:
                src_conn.backup(dest_conn)
            finally:
                dest_conn.close()

        return target_path


_db_instance: DatabaseManager | None = None


def get_db(db_path: str | None = None) -> DatabaseManager:
    """Return singleton DatabaseManager instance."""
    global _db_instance
    if _db_instance is None or db_path is not None:
        _db_instance = DatabaseManager(db_path)
    return _db_instance
