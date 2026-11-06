"""
Memory Manager for OPSRECALL.
Serves as the high-level operational intelligence layer over Hindsight.
Prepares structured incident memories, constructs high-signal recall queries,
extracts historical negative experiences (failed fixes to avoid),
implements multi-factor contextual ranking, transparent retrieval rationales,
and enforces memory safeguards against deduplication, contradictions, and unverified lessons.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from core.hindsight_client import HindsightClientWrapper, get_hindsight_client
from core.validators import (
    FailedApproachWarning,
    Incident,
    RecalledMemoryItem,
    StructuredRetrievalResult,
)

logger = logging.getLogger("opsrecall.memory")


class MemoryManager:
    """Manages operational memory retention, multi-factor recall ranking, and experience extraction."""

    def __init__(self, client: Optional[HindsightClientWrapper] = None):
        self.client = client or get_hindsight_client()
        # Local deduplication cache of document IDs and content hashes
        self._retained_hashes: Dict[str, str] = {}

    @staticmethod
    def format_incident_for_retention(incident: Incident) -> str:
        """
        Format an incident into high-signal structured memory text for Hindsight.
        Preserves complete provenance, timestamps, reviewer identity, and strictly
        segregates unverified suspicions from human-verified root causes.
        """
        lines = [
            f"=== INCIDENT RECORD: {incident.incident_id} ===",
            f"Title: {incident.incident_title}",
            f"Service: {incident.affected_service}",
            f"Severity: {incident.severity}",
            f"Incident Timestamp: {incident.incident_timestamp}",
            f"Verification Status: {'HUMAN_VERIFIED' if incident.is_verified or incident.actual_verified_root_cause else 'UNVERIFIED_TRIAGE'}",
        ]

        if incident.verified_by:
            lines.append(f"Verified By: {incident.verified_by}")
        if incident.verified_at:
            lines.append(f"Verified At: {incident.verified_at}")

        lines.extend([
            "",
            "OPERATIONAL SYMPTOMS:",
        ])
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

        # Strict segregation: Suspected vs Verified
        if incident.suspected_cause:
            lines.append("")
            lines.append(f"[UNVERIFIED INITIAL SUSPICION]: {incident.suspected_cause}")

        if incident.actual_verified_root_cause:
            lines.append("")
            lines.append(f"[HUMAN-VERIFIED ROOT CAUSE]: {incident.actual_verified_root_cause}")
        elif not incident.suspected_cause:
            lines.append("")
            lines.append("[ROOT CAUSE STATUS]: Unconfirmed / Under Investigation")

        if incident.failed_mitigation_attempts:
            lines.append("")
            lines.append("FAILED MITIGATION ATTEMPTS (DO NOT REPEAT):")
            for f in incident.failed_mitigation_attempts:
                lines.append(f"- FAILED FIX: {f}")

        if incident.successful_mitigation or incident.resolution:
            lines.append("")
            lines.append("VERIFIED EFFECTIVE RESOLUTION:")
            if incident.successful_mitigation:
                lines.append(f"- Stabilization Action: {incident.successful_mitigation}")
            if incident.resolution:
                lines.append(f"- Permanent Fix: {incident.resolution}")

        if incident.verification_evidence:
            lines.append("")
            lines.append(f"VERIFICATION EVIDENCE & TELEMETRY PROOF: {incident.verification_evidence}")

        if incident.lessons_learned:
            lines.append("")
            lines.append(f"LESSONS LEARNED: {incident.lessons_learned}")

        lines.append("")
        content_hash = incident.content_hash or incident.compute_content_hash()
        lines.append(f"CONTENT_FINGERPRINT: {content_hash}")
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
        """
        Retain an incident record in Hindsight Cloud with duplicate prevention and provenance.
        """
        content = self.format_incident_for_retention(incident)
        document_id = incident.incident_id
        content_hash = incident.compute_content_hash()

        # Duplicate check safeguard
        if document_id in self._retained_hashes and self._retained_hashes[document_id] == content_hash:
            logger.info(f"Duplicate incident retention skipped for {document_id} (identical content hash).")
            return {
                "success": True,
                "mode": "IDEMPOTENT_SKIPPED",
                "document_id": document_id,
                "items_count": 0,
                "operation_id": None,
                "message": f"Incident {document_id} has identical content hash; retained idempotently.",
            }

        tags = [
            incident.affected_service,
            incident.severity.lower(),
            "incident-experience",
            "verified" if (incident.is_verified or incident.actual_verified_root_cause) else "unverified",
        ]
        metadata = {
            "incident_id": incident.incident_id,
            "service": incident.affected_service,
            "severity": incident.severity,
            "data_type": incident.data_type,
            "is_verified": str(bool(incident.is_verified or incident.actual_verified_root_cause)),
            "content_hash": content_hash,
        }
        if incident.verified_by:
            metadata["verified_by"] = str(incident.verified_by)

        if not self.client.is_configured:
            # Record hash locally
            self._retained_hashes[document_id] = content_hash
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
            self._retained_hashes[document_id] = content_hash
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
        tags_match: str = "any",
        bank_id: Optional[str] = None,
    ) -> List[RecalledMemoryItem]:
        """Recall relevant incident memories from Hindsight."""
        if not self.client.is_configured:
            return []

        try:
            recall_response = self.client.recall(
                query=query,
                max_tokens=max_tokens,
                budget=budget,
                tags=tags,
                tags_match=tags_match,
                bank_id=bank_id,
            )

            results: List[RecalledMemoryItem] = []
            for item in getattr(recall_response, "results", []):
                mem_id = getattr(item, "id", "")
                text = getattr(item, "text", "")
                mem_type = getattr(item, "type", "experience")
                doc_id = getattr(item, "document_id", None)
                mem_tags = getattr(item, "tags", []) or []
                mem_meta = getattr(item, "metadata", {}) or {}

                scores = getattr(item, "scores", None)
                score_val = None
                if scores and hasattr(scores, "relevance") and scores.relevance is not None:
                    try:
                        score_val = float(scores.relevance)
                    except (ValueError, TypeError):
                        score_val = None

                source_inc = doc_id
                if not source_inc and "INC-" in text:
                    match = re.search(r"INC-\d{3}", text)
                    if match:
                        source_inc = match.group(0)

                is_verified = (
                    "HUMAN-VERIFIED" in text or
                    mem_meta.get("is_verified") == "True" or
                    "verified-resolution" in mem_tags
                )

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
                        is_verified=is_verified,
                    )
                )

            return results
        except Exception as e:
            logger.error(f"Hindsight recall failed for query '{query}': {e}")
            return []

    def rank_and_structure_retrievals(
        self,
        recalled_memories: List[RecalledMemoryItem],
        current_service: str,
        current_symptoms: List[str],
        current_errors: List[str],
        current_change: Optional[str] = None,
    ) -> List[StructuredRetrievalResult]:
        """
        Multi-factor ranking and explanation synthesis for recalled memories.
        Combines:
        1. Symptom & token overlap
        2. Error signature alignment
        3. Service context match
        4. Human-verification confidence boost
        5. Negative experience value (failed fix presence)
        6. Domain disambiguation penalty (distinguishing lookalike incidents)
        """
        structured: List[StructuredRetrievalResult] = []
        target_tokens = set()
        for s in current_symptoms:
            target_tokens.update([w.lower() for w in re.findall(r"[a-zA-Z0-9_\-\.]+", s) if len(w) > 3])
        for e in current_errors:
            target_tokens.update([w.lower() for w in re.findall(r"[a-zA-Z0-9_\-\.]+", e) if len(w) > 3])
        if current_change:
            target_tokens.update([w.lower() for w in re.findall(r"[a-zA-Z0-9_\-\.]+", current_change) if len(w) > 3])

        query_str = (" ".join(current_symptoms) + " " + " ".join(current_errors) + " " + str(current_change or "")).lower()

        for mem in recalled_memories:
            text = mem.text
            text_lower = text.lower()
            inc_id = mem.source_incident_id or mem.document_id or "INC-HISTORICAL"
            service = mem.metadata.get("service") or current_service

            # Extract Title if present
            title_match = re.search(r"Title:\s*(.+)", text)
            title = title_match.group(1).strip() if title_match else f"Incident {inc_id}"

            # Factor 1: Token / Symptom Overlap
            mem_tokens = set([w.lower() for w in re.findall(r"[a-zA-Z0-9_\-\.]+", text) if len(w) > 3])
            overlap = len(target_tokens.intersection(mem_tokens))
            symptom_score = min(1.0, overlap / max(1, len(target_tokens) * 0.5))

            # Factor 2: Error Signature Match
            error_sig_score = 0.0
            matching_evidence = []
            distinctive_signatures = [
                ("connection pool", ["pool", "connection checkout", "max_connections"]),
                ("table lock", ["lock", "accessexclusivelock", "lock contention"]),
                ("tls expiry", ["certificate has expired", "tls alert", "ssl handshake"]),
                ("cache stampede", ["cache miss", "stampede", "dog-piling", "redis"]),
                ("partner latency", ["upstream partner", "socket pool exhausted", "paycorp"]),
                ("dns failure", ["coredns", "lookup", "i/o timeout", "10.96.0.10"]),
                ("packet loss", ["tcp retransmit", "syn retransmit", "packet sequence"]),
                ("pdf cpu saturation", ["vector pdf", "invoice", "cpu throttled"]),
                ("node memory pressure", ["nodememorypressure", "memorypressure", "gin index"]),
                ("kafka rebalance", ["max.poll.interval.ms", "preparingrebalance", "rebalance"]),
            ]

            for sig_name, terms in distinctive_signatures:
                query_has = any(t in query_str for t in terms)
                mem_has = any(t in text_lower for t in terms)
                if query_has and mem_has:
                    error_sig_score += 0.4
                    matching_evidence.append(f"Aligned failure signature: {sig_name}")

            # Factor 3: Service Context
            service_score = 0.3 if current_service.lower() in text_lower else 0.0
            if service_score > 0:
                matching_evidence.append(f"Service topology match ({current_service})")

            # Factor 4: Verification Boost
            verification_boost = 0.2 if mem.is_verified else 0.0

            # Factor 5: Negative Experience Value
            has_failed_fixes = "failed fix:" in text_lower or "failed mitigation" in text_lower
            negative_exp_score = 0.15 if has_failed_fixes else 0.0

            # Disambiguation Penalty Safeguard:
            # If current incident has lock contention but memory is connection pool, penalize!
            disambiguation_penalty = 0.0
            if "lock" in query_str and "pool" in text_lower and "lock" not in text_lower:
                disambiguation_penalty = 0.5
            elif "pdf" in query_str and "concurrency" in text_lower and "pdf" not in text_lower:
                disambiguation_penalty = 0.5
            elif "coredns" in query_str and "auth" in text_lower and "dns" not in text_lower:
                disambiguation_penalty = 0.5

            raw_composite = (
                (symptom_score * 0.35) +
                (min(1.0, error_sig_score) * 0.35) +
                service_score +
                verification_boost +
                negative_exp_score -
                disambiguation_penalty
            )
            final_relevance = max(0.0, min(1.0, raw_composite))

            # Extract verified root cause
            v_cause = None
            v_cause_match = re.search(r"\[HUMAN-VERIFIED ROOT CAUSE\]:\s*(.+)", text)
            if v_cause_match:
                v_cause = v_cause_match.group(1).strip()
            elif "VERIFIED ROOT CAUSE:" in text:
                v_cause_match2 = re.search(r"VERIFIED ROOT CAUSE:\s*(.+)", text)
                if v_cause_match2:
                    v_cause = v_cause_match2.group(1).strip()

            # Extract failed mitigations
            failed_fixes = []
            for line in text.splitlines():
                if "FAILED FIX:" in line or "FAILED:" in line:
                    clean_fix = line.replace("FAILED FIX:", "").replace("FAILED:", "").strip("-* ")
                    if clean_fix and len(clean_fix) > 5:
                        failed_fixes.append(clean_fix)

            # Extract effective resolution
            resolution = None
            res_match = re.search(r"-(?:\s*Permanent Fix:|\s*Effective Action:)\s*(.+)", text)
            if res_match:
                resolution = res_match.group(1).strip()

            # Formulate Why Retrieved
            why_retrieved_parts = []
            if matching_evidence:
                why_retrieved_parts.append(f"Retrieved due to {', '.join(matching_evidence[:2])}.")
            else:
                why_retrieved_parts.append(f"Retrieved based on general symptom overlap with service {service}.")
            if failed_fixes:
                why_retrieved_parts.append(f"Contains {len(failed_fixes)} documented negative mitigations to avoid.")
            if mem.is_verified:
                why_retrieved_parts.append("Resolution is human-verified by SRE on-call.")

            why_retrieved = " ".join(why_retrieved_parts)

            structured.append(
                StructuredRetrievalResult(
                    incident_id=inc_id,
                    title=title,
                    service=service,
                    why_retrieved=why_retrieved,
                    matching_evidence=matching_evidence,
                    relevance_score=round(final_relevance, 2),
                    ranking_factors={
                        "symptom_overlap": round(symptom_score, 2),
                        "error_signature": round(min(1.0, error_sig_score), 2),
                        "service_context": round(service_score, 2),
                        "human_verified_bonus": round(verification_boost, 2),
                        "failed_mitigation_bonus": round(negative_exp_score, 2),
                        "disambiguation_penalty": round(disambiguation_penalty, 2),
                    },
                    is_verified=mem.is_verified,
                    verified_by=mem.metadata.get("verified_by"),
                    verified_root_cause=v_cause,
                    failed_mitigations_to_avoid=failed_fixes,
                    effective_resolution=resolution,
                    temporal_recency=mem.timestamp,
                    memory_limitations="Requires manual human verification before applying in production.",
                    raw_memory=mem,
                )
            )

        # Sort descending by composite relevance score
        structured.sort(key=lambda s: s.relevance_score or 0.0, reverse=True)
        return structured

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

            lower_text = text.lower()
            if any(term in lower_text for term in ["failed", "did not solve", "unsuccessful", "exacerbated", "worsened", "do not repeat"]):
                for line in text.splitlines():
                    l_lower = line.lower()
                    if ("failed" in l_lower or "do not" in l_lower or "unsuccessful" in l_lower) and len(line.strip()) > 10:
                        clean_line = line.strip().lstrip("-* ").replace("FAILED FIX:", "").replace("FAILED:", "").replace("FAILED MITIGATION ATTEMPTS (DO NOT REPEAT):", "").strip()
                        if clean_line and clean_line not in seen and not clean_line.startswith("==="):
                            seen.add(clean_line)
                            warnings.append(
                                FailedApproachWarning(
                                    approach=clean_line,
                                    why_failed="Identified as ineffective or harmful in prior incident investigation.",
                                    historical_source_incident=src,
                                    suggested_alternative="Check verified effective resolution in operational memory.",
                                )
                            )

        return warnings

    def detect_contradictions(
        self,
        proposed_action: str,
        recalled_memories: List[RecalledMemoryItem],
    ) -> List[str]:
        """
        Check if a proposed action or hypothesis contradicts known operational memories.
        For example, proposing to flush Redis when prior memory INC-004 proved it causes DB collapse.
        """
        contradictions = []
        prop_lower = proposed_action.lower()

        failed_warnings = self.extract_failed_approaches(recalled_memories)
        for w in failed_warnings:
            approach_words = [w_tok for w_tok in w.approach.lower().split() if len(w_tok) > 4]
            if approach_words and all(tok in prop_lower for tok in approach_words[:2]):
                contradictions.append(
                    f"Action '{proposed_action}' directly contradicts historical postmortem {w.historical_source_incident}: '{w.approach}'"
                )

        return contradictions

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
