"""
Memory Manager for OPSRECALL.
Serves as the high-level operational intelligence layer over Hindsight.
Prepares structured incident memories, constructs high-signal recall queries,
extracts historical negative experiences (failed fixes to avoid),
and maps Hindsight responses into typed data models.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from core.hindsight_client import HindsightClientWrapper, get_hindsight_client
from core.validators import (
    FailedApproachWarning,
    Incident,
    RecalledMemoryItem,
)

logger = logging.getLogger("opsrecall.memory")


class MemoryManager:
    """Manages operational memory retention, recall, and experience extraction."""

    def __init__(self, client: Optional[HindsightClientWrapper] = None):
        self.client = client or get_hindsight_client()

    @staticmethod
    def format_incident_for_retention(incident: Incident) -> str:
        """Format an incident into high-signal structured memory text for Hindsight."""
        lines = [
            f"=== INCIDENT RECORD: {incident.incident_id} ===",
            f"Title: {incident.incident_title}",
            f"Service: {incident.affected_service}",
            f"Severity: {incident.severity}",
            f"Timestamp: {incident.incident_timestamp}",
            "",
            "OPERATIONAL SYMPTOMS:",
        ]
        for s in incident.symptoms:
            lines.append(f"- {s}")

        if incident.error_logs:
            lines.append("")
            lines.append("ERROR LOGS & TRACES:")
            for log in incident.error_logs[:6]:
                lines.append(f"  {log}")

        if incident.metrics:
            lines.append("")
            lines.append(f"OBSERVED METRICS: {incident.metrics}")

        if incident.deployment_id or incident.deployment_or_change:
            lines.append("")
            lines.append("DEPLOYMENT & CHANGE CONTEXT:")
            if incident.deployment_id:
                lines.append(f"- Deployment ID: {incident.deployment_id}")
            if incident.deployment_or_change:
                lines.append(f"- Change Details: {incident.deployment_or_change}")

        if incident.suspected_cause:
            lines.append("")
            lines.append(f"INITIAL SUSPICION: {incident.suspected_cause}")

        if incident.actual_verified_root_cause:
            lines.append("")
            lines.append(f"VERIFIED ROOT CAUSE: {incident.actual_verified_root_cause}")

        if incident.failed_mitigation_attempts:
            lines.append("")
            lines.append("FAILED MITIGATION ATTEMPTS (DO NOT REPEAT):")
            for f in incident.failed_mitigation_attempts:
                lines.append(f"- FAILED FIX: {f}")

        if incident.successful_mitigation or incident.resolution:
            lines.append("")
            lines.append("SUCCESSFUL RESOLUTION & MITIGATION:")
            if incident.successful_mitigation:
                lines.append(f"- Effective Action: {incident.successful_mitigation}")
            if incident.resolution:
                lines.append(f"- Permanent Resolution: {incident.resolution}")

        if incident.verification_evidence:
            lines.append("")
            lines.append(f"VERIFICATION EVIDENCE: {incident.verification_evidence}")

        if incident.lessons_learned:
            lines.append("")
            lines.append(f"LESSONS LEARNED: {incident.lessons_learned}")

        lines.append("")
        lines.append(f"CLASSIFICATION: {incident.data_type}")
        return "\n".join(lines)

    @staticmethod
    def build_recall_query(
        service: str,
        symptoms: List[str],
        error_logs: List[str],
        deployment_change: Optional[str] = None,
    ) -> str:
        """Construct a high-signal search query from current incident symptoms and changes."""
        parts = [f"Service: {service}"]

        if deployment_change:
            parts.append(f"Deployment change: {deployment_change}")

        if symptoms:
            parts.append("Symptoms: " + "; ".join(symptoms[:3]))

        if error_logs:
            # Extract distinctive error messages
            first_err = error_logs[0][:200]
            parts.append(f"Errors: {first_err}")

        parts.append("What was the verified root cause, failed mitigations, and successful resolution?")
        return " | ".join(parts)

    def retain_incident(
        self,
        incident: Incident,
        bank_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retain an incident record in Hindsight Cloud."""
        content = self.format_incident_for_retention(incident)
        document_id = incident.incident_id
        tags = [
            incident.affected_service,
            incident.severity.lower(),
            "incident-experience",
            "verified-resolution",
        ]
        metadata = {
            "incident_id": incident.incident_id,
            "service": incident.affected_service,
            "severity": incident.severity,
            "data_type": incident.data_type,
        }

        if not self.client.is_configured:
            return {
                "success": False,
                "mode": "OFFLINE_UNCONFIGURED",
                "document_id": document_id,
                "items_count": 0,
                "operation_id": None,
                "message": "Hindsight is not configured. Experience recorded locally only.",
            }

        try:
            resp = self.client.retain(
                content=content,
                document_id=document_id,
                metadata=metadata,
                tags=tags,
                timestamp=incident.incident_timestamp,
                bank_id=bank_id,
            )
            return {
                "success": getattr(resp, "success", True),
                "mode": "LIVE_HINDSIGHT",
                "document_id": document_id,
                "items_count": getattr(resp, "items_count", 1),
                "operation_id": getattr(resp, "operation_id", None),
                "message": f"Successfully retained incident {document_id} into Hindsight.",
            }
        except Exception as e:
            logger.error(f"Hindsight retain failed for {document_id}: {e}")
            return {
                "success": False,
                "mode": "ERROR",
                "document_id": document_id,
                "items_count": 0,
                "operation_id": None,
                "error": str(e),
                "message": f"Hindsight retain operation encountered an error: {e}",
            }

    def recall_memories(
        self,
        query: str,
        max_tokens: int = 4096,
        budget: str = "mid",
        tags: Optional[List[str]] = None,
        bank_id: Optional[str] = None,
    ) -> List[RecalledMemoryItem]:
        """Recall relevant incident memories from Hindsight."""
        if not self.client.is_configured:
            # When Hindsight is not configured, return empty list so the app
            # never fabricates fake Hindsight retrievals
            return []

        try:
            recall_response = self.client.recall(
                query=query,
                max_tokens=max_tokens,
                budget=budget,
                tags=tags,
                bank_id=bank_id,
            )

            results: List[RecalledMemoryItem] = []
            for item in getattr(recall_response, "results", []):
                # Inspect fields on RecallResult
                mem_id = getattr(item, "id", "")
                text = getattr(item, "text", "")
                mem_type = getattr(item, "type", "experience")
                doc_id = getattr(item, "document_id", None)
                mem_tags = getattr(item, "tags", []) or []
                mem_meta = getattr(item, "metadata", {}) or {}

                # Relevance score if available
                scores = getattr(item, "scores", None)
                score_val = None
                if scores and hasattr(scores, "relevance"):
                    score_val = float(scores.relevance)

                # Extract incident ID from text or document_id if present
                source_inc = doc_id
                if not source_inc and "INC-" in text:
                    match = re.search(r"INC-\d{3}", text)
                    if match:
                        source_inc = match.group(0)

                results.append(
                    RecalledMemoryItem(
                        memory_id=mem_id,
                        text=text,
                        memory_type=mem_type,
                        document_id=doc_id,
                        tags=mem_tags,
                        metadata=mem_meta,
                        relevance_score=score_val,
                        source_incident_id=source_inc,
                        timestamp=getattr(item, "mentioned_at", None),
                    )
                )

            return results
        except Exception as e:
            logger.error(f"Hindsight recall failed for query '{query}': {e}")
            return []

    def extract_failed_approaches(
        self,
        recalled_memories: List[RecalledMemoryItem],
    ) -> List[FailedApproachWarning]:
        """Scan recalled memories to isolate historical failed fixes to avoid."""
        warnings: List[FailedApproachWarning] = []
        seen = set()

        for mem in recalled_memories:
            text = mem.text
            src = mem.source_incident_id or mem.document_id or "Historical Incident"

            # Check if text mentions failed mitigation or unsuccessful fix
            lower_text = text.lower()
            if any(term in lower_text for term in ["failed", "did not solve", "unsuccessful", "exacerbated", "worsened"]):
                # Split lines or sentences
                for line in text.splitlines():
                    l_lower = line.lower()
                    if ("failed" in l_lower or "do not" in l_lower or "unsuccessful" in l_lower) and len(line.strip()) > 10:
                        clean_line = line.strip().lstrip("-* ").replace("FAILED FIX:", "").replace("FAILED:", "").strip()
                        if clean_line and clean_line not in seen:
                            seen.add(clean_line)
                            warnings.append(
                                FailedApproachWarning(
                                    approach=clean_line,
                                    why_failed="Identified as unsuccessful in prior incident investigation.",
                                    historical_source_incident=src,
                                )
                            )

        return warnings

    def reflect_patterns(
        self,
        query: str,
        budget: str = "mid",
        context: Optional[str] = None,
        bank_id: Optional[str] = None,
    ) -> Optional[str]:
        """Run Hindsight reflection to identify macro incident patterns."""
        if not self.client.is_configured:
            return None

        try:
            resp = self.client.reflect(
                query=query,
                budget=budget,
                context=context,
                bank_id=bank_id,
            )
            return getattr(resp, "text", str(resp))
        except Exception as e:
            logger.error(f"Hindsight reflect failed: {e}")
            return None


_memory_manager_instance: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Singleton getter for MemoryManager."""
    global _memory_manager_instance
    if _memory_manager_instance is None:
        _memory_manager_instance = MemoryManager()
    return _memory_manager_instance

