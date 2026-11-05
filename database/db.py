"""
SQLite database manager for OPSRECALL local state persistence.
Stores local incident cache, audit logs of investigations, human-verified resolutions,
and benchmark experiment records.
NOTE: SQLite acts as an audit log / local record-keeper and NEVER substitutes for Hindsight memory.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from config import settings
from core.validators import Incident, InvestigationResult, ResolutionFeedback, CaseEvaluationScore


class DatabaseManager:
    """Manages SQLite connection and schemas for OPSRECALL local audit records."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or settings.SQLITE_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a SQLite connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_schema(self) -> None:
        """Initialize required database tables if they do not exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Incidents table
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
                    diagnostic_actions_attempted TEXT,
                    failed_mitigation_attempts TEXT,
                    successful_mitigation TEXT,
                    resolution TEXT,
                    resolution_outcome TEXT,
                    verification_evidence TEXT,
                    lessons_learned TEXT,
                    data_type TEXT DEFAULT 'SIMULATED_INCIDENT',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Investigations table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS investigations (
                    investigation_id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    executive_summary TEXT,
                    hypotheses TEXT NOT NULL,
                    recalled_memories TEXT,
                    historical_incidents_referenced TEXT,
                    recommended_remediation_steps TEXT,
                    confidence_level TEXT,
                    llm_model TEXT,
                    execution_time_seconds REAL,
                    created_at TEXT NOT NULL,
                    raw_result TEXT NOT NULL
                )
                """
            )

            # Human-verified resolutions table
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
                    retained_to_hindsight INTEGER DEFAULT 0,
                    hindsight_operation_id TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

            # Evaluation runs table
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

            # Evaluation case details
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    memory_mode TEXT NOT NULL,
                    top_3_root_cause_hit INTEGER NOT NULL,
                    retrieved_expected_historical INTEGER NOT NULL,
                    recalled_failed_mitigations INTEGER NOT NULL,
                    avoided_unsuccessful_mitigations INTEGER NOT NULL,
                    false_recall_flagged INTEGER NOT NULL,
                    appropriate_uncertainty INTEGER NOT NULL,
                    overall_score REAL NOT NULL,
                    explanation TEXT,
                    FOREIGN KEY (run_id) REFERENCES evaluation_runs (run_id)
                )
                """
            )

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
                    diagnostic_actions_attempted, failed_mitigation_attempts,
                    successful_mitigation, resolution, resolution_outcome,
                    verification_evidence, lessons_learned, data_type, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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
                    json.dumps(incident.diagnostic_actions_attempted),
                    json.dumps(incident.failed_mitigation_attempts),
                    incident.successful_mitigation,
                    incident.resolution,
                    incident.resolution_outcome,
                    incident.verification_evidence,
                    incident.lessons_learned,
                    incident.data_type,
                ),
            )
            conn.commit()

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Fetch an incident by its ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM incidents WHERE incident_id = ?", (incident_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_incident(row)

    def list_incidents(self) -> List[Incident]:
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
                    investigation_id, incident_id, mode, executive_summary,
                    hypotheses, recalled_memories, historical_incidents_referenced,
                    recommended_remediation_steps, confidence_level, llm_model,
                    execution_time_seconds, created_at, raw_result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.investigation_id,
                    result.incident_id,
                    result.mode,
                    result.executive_summary,
                    json.dumps([h.model_dump() for h in result.hypotheses]),
                    json.dumps([m.model_dump() for m in result.recalled_memories]),
                    json.dumps(result.historical_incidents_referenced),
                    json.dumps([r.model_dump() for r in result.recommended_remediation_steps]),
                    result.confidence_level,
                    result.llm_model,
                    result.execution_time_seconds,
                    result.created_at,
                    result.model_dump_json(),
                ),
            )
            conn.commit()

    def list_investigations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent investigations."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT investigation_id, incident_id, mode, executive_summary,
                       confidence_level, llm_model, execution_time_seconds, created_at
                FROM investigations
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def save_resolution(self, feedback: ResolutionFeedback) -> int:
        """Save a human-confirmed incident resolution."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO resolutions (
                    incident_id, verified_root_cause, successful_resolution,
                    failed_approaches, verification_evidence, lessons_learned,
                    verified_by, retained_to_hindsight, hindsight_operation_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback.incident_id,
                    feedback.verified_root_cause,
                    feedback.successful_resolution,
                    json.dumps(feedback.failed_approaches),
                    feedback.verification_evidence,
                    feedback.lessons_learned,
                    feedback.verified_by,
                    1 if feedback.retained_to_hindsight else 0,
                    feedback.hindsight_operation_id,
                    feedback.created_at,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def list_resolutions(self, limit: int = 20) -> List[Dict[str, Any]]:
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
        summary_json: Dict[str, Any],
        details: List[CaseEvaluationScore],
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
                        run_id, case_id, memory_mode, top_3_root_cause_hit,
                        retrieved_expected_historical, recalled_failed_mitigations,
                        avoided_unsuccessful_mitigations, false_recall_flagged,
                        appropriate_uncertainty, overall_score, explanation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        d.case_id,
                        d.memory_mode,
                        1 if d.top_3_root_cause_hit else 0,
                        1 if d.retrieved_expected_historical else 0,
                        1 if d.recalled_failed_mitigations else 0,
                        1 if d.avoided_unsuccessful_mitigations else 0,
                        1 if d.false_recall_flagged else 0,
                        1 if d.appropriate_uncertainty else 0,
                        d.overall_score,
                        d.explanation,
                    ),
                )
            conn.commit()

    def get_latest_evaluation_run(self) -> Optional[Dict[str, Any]]:
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
            symptoms=json.loads(row["symptoms"]),
            error_logs=json.loads(row["error_logs"]),
            metrics=json.loads(row["metrics"]),
            deployment_id=row["deployment_id"],
            deployment_or_change=row["deployment_or_change"],
            suspected_cause=row["suspected_cause"],
            actual_verified_root_cause=row["actual_verified_root_cause"],
            diagnostic_actions_attempted=json.loads(row["diagnostic_actions_attempted"]),
            failed_mitigation_attempts=json.loads(row["failed_mitigation_attempts"]),
            successful_mitigation=row["successful_mitigation"],
            resolution=row["resolution"],
            resolution_outcome=row["resolution_outcome"],
            verification_evidence=row["verification_evidence"],
            lessons_learned=row["lessons_learned"],
            data_type=row["data_type"],
        )


_db_instance: Optional[DatabaseManager] = None


def get_db(db_path: Optional[str] = None) -> DatabaseManager:
    """Return singleton DatabaseManager instance."""
    global _db_instance
    if _db_instance is None or db_path is not None:
        _db_instance = DatabaseManager(db_path)
    return _db_instance

