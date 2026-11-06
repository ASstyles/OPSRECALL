"""
Learning Engine for OPSRECALL.
Captures human-confirmed incident resolutions, failed approaches,
and verified root causes, then retains the newly acquired operational experience
into Hindsight persistent memory and local audit tables through a multi-stage verified pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from core.incident_engine import get_incident_engine
from core.memory_manager import MemoryManager, get_memory_manager
from core.validators import Incident, ResolutionFeedback
from database.db import DatabaseManager, get_db

logger = logging.getLogger("opsrecall.learning")


class LearningEngine:
    """Manages post-incident learning, human confirmation, conflict detection, and Hindsight retention."""

    def __init__(
        self,
        memory_manager: MemoryManager | None = None,
        db: DatabaseManager | None = None,
    ):
        self.memory_manager = memory_manager or get_memory_manager()
        self.db = db or get_db()
        self.incident_engine = get_incident_engine()

    def confirm_and_retain_resolution(
        self,
        incident_id: str,
        verified_root_cause: str,
        successful_resolution: str,
        failed_approaches: list[str],
        verification_evidence: str,
        lessons_learned: str,
        verified_by: str = "SRE On-Call Engineer",
    ) -> dict[str, Any]:
        """
        Record verified resolution and retain knowledge into Hindsight through a multi-stage pipeline:
        Stage 1: FEEDBACK_RECEIVED
        Stage 2: FEEDBACK_VALIDATED
        Stage 3: CONFLICT_DETECTION (checks if new feedback contradicts prior confirmed root cause)
        Stage 4: LOCAL_AUDIT_SAVED
        Stage 5: HINDSIGHT_RETENTION_ATTEMPTED
        Stage 6: HINDSIGHT_RETENTION_CONFIRMED & MEMORY_RETRIEVABLE
        """
        # Stage 1: Validation
        if not incident_id or not incident_id.strip():
            raise ValueError("Incident ID cannot be empty.")
        if not verified_root_cause or not verified_root_cause.strip():
            raise ValueError("Verified root cause must be specified before confirming resolution.")
        if not successful_resolution or not successful_resolution.strip():
            raise ValueError("Successful resolution must be specified before confirming resolution.")

        clean_inc_id = incident_id.strip()
        clean_cause = verified_root_cause.strip()
        clean_res = successful_resolution.strip()
        clean_evidence = verification_evidence.strip()
        clean_lessons = lessons_learned.strip()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Stage 2: Fetch original incident and check for conflicts
        incident = self.incident_engine.get_incident(clean_inc_id)
        conflict_detected = False
        conflict_details = None

        if incident:
            prior_cause = incident.actual_verified_root_cause
            if prior_cause and prior_cause.lower() != clean_cause.lower():
                conflict_detected = True
                conflict_details = (
                    f"Conflicting root cause update: Previous confirmed cause was '{prior_cause}'. "
                    f"New verified cause submitted by {verified_by}: '{clean_cause}'."
                )
                logger.warning(f"Incident {clean_inc_id} conflict detected: {conflict_details}")
        else:
            incident = Incident(
                incident_id=clean_inc_id,
                incident_title=f"Resolved Incident {clean_inc_id}",
                affected_service="general-service",
                severity="SEV-2",
                symptoms=["Operational anomaly resolved by human engineer"],
            )

        # Update incident record with human-confirmed truths
        incident.actual_verified_root_cause = clean_cause
        incident.is_verified = True
        incident.verified_by = verified_by
        incident.verified_at = now_iso
        incident.successful_mitigation = clean_res
        incident.resolution = clean_res
        incident.resolution_outcome = "Human-Verified and Resolved"
        incident.failed_mitigation_attempts = list(
            set(incident.failed_mitigation_attempts + [f.strip() for f in failed_approaches if f.strip()])
        )
        incident.verification_evidence = clean_evidence
        incident.lessons_learned = clean_lessons

        # Stage 4: Save updated incident to SQLite
        self.incident_engine.save_incident(incident)

        # Stage 5: Retain into Hindsight persistent memory
        status = "FEEDBACK_VALIDATED"
        retained_ok = False
        op_id = None
        error_msg = None

        if self.memory_manager.client.is_configured:
            status = "HINDSIGHT_RETENTION_ATTEMPTED"
            retain_res = self.memory_manager.retain_incident(incident)
            retained_ok = retain_res.get("success", False)
            op_id = retain_res.get("operation_id")
            mode = retain_res.get("mode", "LIVE_HINDSIGHT")

            if retained_ok:
                status = "HINDSIGHT_RETENTION_CONFIRMED"
                # Check indexing status with bounded wait
                is_indexed = self.memory_manager.client.wait_for_document_processing(
                    document_id=clean_inc_id,
                    timeout_seconds=5.0,
                    poll_interval=1.0,
                )
                if is_indexed:
                    status = "MEMORY_RETRIEVABLE"
            else:
                status = "RETENTION_FAILED"
                error_msg = retain_res.get("error") or retain_res.get("message")
        else:
            status = "LOCAL_AUDIT_SAVED"
            mode = "OFFLINE_UNCONFIGURED"

        # Create feedback record
        feedback = ResolutionFeedback(
            incident_id=clean_inc_id,
            verified_root_cause=clean_cause,
            successful_resolution=clean_res,
            failed_approaches=failed_approaches,
            verification_evidence=clean_evidence,
            lessons_learned=clean_lessons,
            verified_by=verified_by,
            is_verified=True,
            status=status,
            retained_to_hindsight=retained_ok,
            hindsight_operation_id=op_id,
            error_message=error_msg,
            conflict_detected=conflict_detected,
            conflict_details=conflict_details,
            created_at=now_iso,
        )

        row_id = self.db.save_resolution(feedback)

        # Generate truthful, non-misleading response message
        if status in ("HINDSIGHT_RETENTION_CONFIRMED", "MEMORY_RETRIEVABLE"):
            msg = f"Incident {clean_inc_id} successfully confirmed by {verified_by} and retained into Hindsight Cloud [{status}]."
        elif status == "LOCAL_AUDIT_SAVED":
            msg = (
                f"Incident {clean_inc_id} confirmed by {verified_by} and saved to local audit database. "
                "Hindsight Cloud is unconfigured, so cloud retention was skipped (Offline Preview Mode)."
            )
        else:
            msg = f"Incident {clean_inc_id} saved locally, but Hindsight retention failed: {error_msg}"

        return {
            "success": retained_ok or (status == "LOCAL_AUDIT_SAVED"),
            "resolution_id": row_id,
            "incident_id": clean_inc_id,
            "status": status,
            "retained_to_hindsight": retained_ok,
            "hindsight_mode": mode,
            "hindsight_operation_id": op_id,
            "conflict_detected": conflict_detected,
            "conflict_details": conflict_details,
            "verified_by": verified_by,
            "message": msg,
        }

    def get_learning_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieve recent human-verified incident resolutions."""
        return self.db.list_resolutions(limit=limit)


_learning_engine_instance: LearningEngine | None = None


def get_learning_engine() -> LearningEngine:
    """Singleton getter for LearningEngine."""
    global _learning_engine_instance
    if _learning_engine_instance is None:
        _learning_engine_instance = LearningEngine()
    return _learning_engine_instance
