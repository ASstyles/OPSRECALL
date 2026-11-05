"""
Learning Engine for OPSRECALL.
Captures human-confirmed incident resolutions, failed approaches,
and verified root causes, then retains the newly acquired operational experience
into Hindsight persistent memory and local audit tables.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from core.incident_engine import get_incident_engine
from core.memory_manager import MemoryManager, get_memory_manager
from core.validators import Incident, ResolutionFeedback
from database.db import DatabaseManager, get_db

logger = logging.getLogger("opsrecall.learning")


class LearningEngine:
    """Manages post-incident learning, human confirmation, and Hindsight retention."""

    def __init__(
        self,
        memory_manager: Optional[MemoryManager] = None,
        db: Optional[DatabaseManager] = None,
    ):
        self.memory_manager = memory_manager or get_memory_manager()
        self.db = db or get_db()
        self.incident_engine = get_incident_engine()

    def confirm_and_retain_resolution(
        self,
        incident_id: str,
        verified_root_cause: str,
        successful_resolution: str,
        failed_approaches: List[str],
        verification_evidence: str,
        lessons_learned: str,
        verified_by: str = "SRE On-Call Engineer",
    ) -> Dict[str, Any]:
        """
        Record verified resolution and retain knowledge into Hindsight.

        Workflow:
        1. Create ResolutionFeedback object.
        2. Update existing incident record with confirmed details.
        3. Format and retain verified experience into Hindsight Cloud.
        4. Record resolution in local SQLite audit table.
        5. Return comprehensive retention confirmation.
        """
        # Fetch original incident or create a stub if custom
        incident = self.incident_engine.get_incident(incident_id)
        if not incident:
            incident = Incident(
                incident_id=incident_id,
                incident_title=f"Resolved Incident {incident_id}",
                affected_service="general-service",
                severity="SEV-2",
                symptoms=["Operational anomaly resolved by human engineer"],
            )

        # Update incident record with human-confirmed truths
        incident.actual_verified_root_cause = verified_root_cause
        incident.successful_mitigation = successful_resolution
        incident.resolution = successful_resolution
        incident.resolution_outcome = "Human-Verified and Resolved"
        incident.failed_mitigation_attempts = list(
            set(incident.failed_mitigation_attempts + failed_approaches)
        )
        incident.verification_evidence = verification_evidence
        incident.lessons_learned = lessons_learned

        # Save updated incident to SQLite
        self.incident_engine.save_incident(incident)

        # Retain into Hindsight persistent memory
        retain_res = self.memory_manager.retain_incident(incident)

        retained_ok = retain_res.get("success", False)
        op_id = retain_res.get("operation_id")
        mode = retain_res.get("mode", "UNKNOWN")

        # Create feedback record
        feedback = ResolutionFeedback(
            incident_id=incident_id,
            verified_root_cause=verified_root_cause,
            successful_resolution=successful_resolution,
            failed_approaches=failed_approaches,
            verification_evidence=verification_evidence,
            lessons_learned=lessons_learned,
            verified_by=verified_by,
            retained_to_hindsight=retained_ok,
            hindsight_operation_id=op_id,
        )

        row_id = self.db.save_resolution(feedback)

        return {
            "success": True,
            "resolution_id": row_id,
            "incident_id": incident_id,
            "retained_to_hindsight": retained_ok,
            "hindsight_mode": mode,
            "hindsight_operation_id": op_id,
            "message": (
                f"Incident {incident_id} successfully confirmed. "
                f"Operational memory retained to Hindsight [{mode}]."
            ),
        }

    def get_learning_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent human-verified incident resolutions."""
        return self.db.list_resolutions(limit=limit)


_learning_engine_instance: Optional[LearningEngine] = None


def get_learning_engine() -> LearningEngine:
    """Singleton getter for LearningEngine."""
    global _learning_engine_instance
    if _learning_engine_instance is None:
        _learning_engine_instance = LearningEngine()
    return _learning_engine_instance

