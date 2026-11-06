"""
Incident Engine for OPSRECALL.
Responsible for loading, validating, and managing synthetic incident datasets.
All synthetic incidents are explicitly tagged with SIMULATED_HISTORICAL_INCIDENT.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import settings
from core.validators import Incident
from database.db import get_db


class IncidentEngine:
    """Manages synthetic incident repository and operational incident ingestion."""

    def __init__(self, incidents_path: Path | None = None):
        self.incidents_path = incidents_path or settings.INCIDENTS_PATH
        self.db = get_db()
        self._ensure_dataset_loaded()

    def _ensure_dataset_loaded(self) -> None:
        """Ensure initial synthetic incidents from data/incidents.json are in DB."""
        if not self.incidents_path.exists():
            return

        try:
            with open(self.incidents_path, encoding="utf-8") as f:
                data = json.load(f)

            for item in data:
                incident = Incident(**item)
                # Save to database
                self.db.upsert_incident(incident)
        except Exception as e:
            print(f"[IncidentEngine] Warning: Failed to preload incidents: {e}")

    def get_all_incidents(self) -> list[Incident]:
        """Retrieve all incidents currently stored in the system."""
        incidents = self.db.list_incidents()
        if not incidents and self.incidents_path.exists():
            self._ensure_dataset_loaded()
            incidents = self.db.list_incidents()
        return incidents

    def get_incident(self, incident_id: str) -> Incident | None:
        """Fetch a single incident by ID."""
        return self.db.get_incident(incident_id)

    def save_incident(self, incident: Incident) -> None:
        """Validate and persist an incident."""
        self.db.upsert_incident(incident)

    def get_service_health_summary(self) -> list[dict[str, Any]]:
        """Compute service status summary from stored incidents."""
        incidents = self.get_all_incidents()
        services: dict[str, dict[str, Any]] = {}

        for inc in incidents:
            svc = inc.affected_service
            if svc not in services:
                services[svc] = {
                    "service_name": svc,
                    "incident_count": 0,
                    "sev1_count": 0,
                    "latest_incident_time": inc.incident_timestamp,
                    "latest_severity": inc.severity,
                }
            services[svc]["incident_count"] += 1
            if inc.severity == "SEV-1":
                services[svc]["sev1_count"] += 1

        return list(services.values())


_incident_engine_instance: IncidentEngine | None = None


def get_incident_engine() -> IncidentEngine:
    """Return singleton instance of IncidentEngine."""
    global _incident_engine_instance
    if _incident_engine_instance is None:
        _incident_engine_instance = IncidentEngine()
    return _incident_engine_instance
