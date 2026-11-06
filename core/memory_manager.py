"""
Memory Manager for OPSRECALL.
Serves as the high-level operational intelligence layer over Hindsight.
Prepares structured incident memories, constructs high-signal recall queries,
extracts historical negative experiences (failed fixes to avoid),
implements multi-factor contextual ranking, transparent retrieval rationales,
and enforces memory safeguards against deduplication, contradictions, and unverified lessons.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from core.hindsight_client import HindsightClientWrapper, get_hindsight_client
from core.validators import (
    ActionEquivalenceEvaluation,
    ActionIntent,
    CanonicalRetrievalCandidate,
    FailedApproachWarning,
    Incident,
    RecalledMemoryItem,
    StructuredRetrievalResult,
)

logger = logging.getLogger("opsrecall.memory")


# SRE Operational Action Semantic Clusters for Equivalence Matching and Risk Detection
ACTION_SEMANTIC_CLUSTERS: dict[str, dict[str, Any]] = {
    "HORIZONTAL_SCALE": {
        "intent": "Expand application or worker replica count",
        "keywords": [
            "scale",
            "replicas",
            "hpa",
            "autoscale",
            "instances",
            "worker pool",
            "horizontal scale",
            "add pods",
            "scale out",
        ],
        "harmful_symptoms": [
            "nodememorypressure",
            "max_connections",
            "connection pool",
            "lock contention",
            "table lock",
            "database cpu",
        ],
        "failure_explanation": (
            "Scaling worker replicas increases load or memory pressure without addressing the underlying bottleneck."
        ),
    },
    "CACHE_FLUSH": {
        "intent": "Flush or purge in-memory cache",
        "keywords": [
            "flush",
            "flushall",
            "flushdb",
            "clear cache",
            "purge cache",
            "evict keys",
            "redis-cli flush",
        ],
        "harmful_symptoms": [
            "cache miss",
            "stampede",
            "database cpu",
            "connection pool",
            "high qps",
            "dog-piling",
        ],
        "failure_explanation": (
            "Flushing cache under load causes instantaneous cache stampede and saturates backend database."
        ),
    },
    "RETRY_AGGRESSIVE": {
        "intent": "Increase client retry count or decrease backoff delay",
        "keywords": [
            "retry count",
            "max retries",
            "retry limit",
            "retry immediately",
            "shorten backoff",
            "increase retries",
        ],
        "harmful_symptoms": [
            "cascading",
            "timeout cascade",
            "upstream latency",
            "socket pool",
            "retry storm",
            "504 gateway",
        ],
        "failure_explanation": ("Aggressive retries amplify traffic against already failing upstream dependencies."),
    },
    "RESTART_PODS": {
        "intent": "Rollout restart or kill deployment instances",
        "keywords": [
            "restart",
            "rollout restart",
            "kill pod",
            "reboot deployment",
            "redeploy",
        ],
        "harmful_symptoms": [
            "table lock",
            "ddl migration",
            "lock contention",
            "schema lock",
            "deadlock",
        ],
        "failure_explanation": (
            "Restarting application instances during database lock contention causes all pods to pile up in startup checkouts."
        ),
    },
    "POOL_EXPANSION_OVERCOMMIT": {
        "intent": "Increase database connection pool size",
        "keywords": [
            "max_connections",
            "max_pool_size",
            "expand pool",
            "raise connection limit",
            "increase pool size",
            "pool capacity",
        ],
        "harmful_symptoms": [
            "database cpu",
            "db memory",
            "pg_stat_activity",
            "postgres memory",
            "oom",
        ],
        "failure_explanation": (
            "Expanding client connection pools when database is already saturated causes Postgres connection thrashing and OOM."
        ),
    },
}


def _match_term(terms: list[str], text: str) -> bool:
    """Helper to match multi-word phrases by substring and single words by regex boundary."""
    for term in terms:
        if " " in term or "-" in term or "_" in term:
            if term in text:
                return True
        else:
            if re.search(rf"\b{re.escape(term)}\b", text):
                return True
    return False


class MemoryManager:
    """Manages operational memory retention, multi-factor recall ranking, and experience extraction."""

    def __init__(self, client: HindsightClientWrapper | None = None):
        self.client = client or get_hindsight_client()
        # Local deduplication cache of document IDs and content hashes
        self._retained_hashes: dict[str, str] = {}

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

        lines.extend(
            [
                "",
                "OPERATIONAL SYMPTOMS:",
            ]
        )
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
        symptoms: list[str],
        error_logs: list[str],
        deployment_change: str | None = None,
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
        bank_id: str | None = None,
    ) -> dict[str, Any]:
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
        tags: list[str] | None = None,
        tags_match: str = "any",
        bank_id: str | None = None,
    ) -> list[RecalledMemoryItem]:
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

            results: list[RecalledMemoryItem] = []
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
                    "HUMAN-VERIFIED" in text
                    or mem_meta.get("is_verified") == "True"
                    or "verified-resolution" in mem_tags
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
        recalled_memories: list[RecalledMemoryItem],
        current_service: str,
        current_symptoms: list[str],
        current_errors: list[str],
        current_change: str | None = None,
    ) -> list[StructuredRetrievalResult]:
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
        structured: list[StructuredRetrievalResult] = []
        target_tokens = set()
        for s in current_symptoms:
            target_tokens.update([w.lower() for w in re.findall(r"[a-zA-Z0-9_\-\.]+", s) if len(w) > 3])
        for e in current_errors:
            target_tokens.update([w.lower() for w in re.findall(r"[a-zA-Z0-9_\-\.]+", e) if len(w) > 3])
        if current_change:
            target_tokens.update([w.lower() for w in re.findall(r"[a-zA-Z0-9_\-\.]+", current_change) if len(w) > 3])

        query_str = (
            " ".join(current_symptoms) + " " + " ".join(current_errors) + " " + str(current_change or "")
        ).lower()

        for mem in recalled_memories:
            text = mem.text
            text_lower = text.lower()
            inc_id = mem.source_incident_id or mem.document_id or "INC-HISTORICAL"
            service = mem.metadata.get("service") or current_service

            # Extract Title if present
            title_match = re.search(r"Title:\s*(.+)", text)
            title = title_match.group(1).strip() if title_match else f"Incident {inc_id}"

            # Factor 1: Token / Symptom Overlap
            mem_tokens = {w.lower() for w in re.findall(r"[a-zA-Z0-9_\-\.]+", text) if len(w) > 3}
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
                (symptom_score * 0.35)
                + (min(1.0, error_sig_score) * 0.35)
                + service_score
                + verification_boost
                + negative_exp_score
                - disambiguation_penalty
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

        # Sort descending by composite relevance score and assign canonical ranks
        structured.sort(key=lambda s: s.relevance_score or 0.0, reverse=True)
        for idx, item in enumerate(structured, start=1):
            item.rank = idx
        return structured

    def to_canonical_candidates(
        self,
        structured_retrievals: list[StructuredRetrievalResult],
    ) -> list[CanonicalRetrievalCandidate]:
        """Convert structured retrievals to canonical ranked candidates preserving exact order."""
        return [
            CanonicalRetrievalCandidate(
                candidate_id=sr.incident_id,
                source_incident_id=sr.incident_id,
                rank=sr.rank,
                relevance_score=sr.relevance_score or 0.0,
                ranking_factors=sr.ranking_factors,
                source="HINDSIGHT",
                is_verified=sr.is_verified,
                retrieval_reason=sr.why_retrieved,
            )
            for sr in structured_retrievals
        ]

    def extract_failed_approaches(
        self,
        recalled_memories: list[RecalledMemoryItem],
    ) -> list[FailedApproachWarning]:
        """Scan recalled memories to isolate historical failed fixes to avoid."""
        warnings: list[FailedApproachWarning] = []
        seen = set()

        for mem in recalled_memories:
            text = mem.text
            src = mem.source_incident_id or mem.document_id or "Historical Incident"

            lower_text = text.lower()
            if any(
                term in lower_text
                for term in ["failed", "did not solve", "unsuccessful", "exacerbated", "worsened", "do not repeat"]
            ):
                for line in text.splitlines():
                    l_lower = line.lower()
                    if ("failed" in l_lower or "do not" in l_lower or "unsuccessful" in l_lower) and len(
                        line.strip()
                    ) > 10:
                        clean_line = (
                            line.strip()
                            .lstrip("-* ")
                            .replace("FAILED FIX:", "")
                            .replace("FAILED:", "")
                            .replace("FAILED MITIGATION ATTEMPTS (DO NOT REPEAT):", "")
                            .strip()
                        )
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

    def extract_successful_resolutions(
        self,
        recalled_memories: list[RecalledMemoryItem],
    ) -> list[dict[str, str]]:
        """Extract verified effective resolutions from recalled memories."""
        resolutions = []
        for mem in recalled_memories:
            text = mem.text
            src = mem.source_incident_id or mem.document_id or "Historical Incident"
            for line in text.splitlines():
                if any(
                    k in line for k in ["Permanent Fix:", "Stabilization Action:", "VERIFIED EFFECTIVE RESOLUTION:"]
                ):
                    clean = (
                        line.replace("Permanent Fix:", "")
                        .replace("Stabilization Action:", "")
                        .replace("VERIFIED EFFECTIVE RESOLUTION:", "")
                        .strip("-* ")
                    )
                    if clean and len(clean) > 8:
                        resolutions.append({"resolution": clean, "source": src})
        return resolutions

    @classmethod
    def normalize_action_intent(cls, action_text: str, service: str | None = None) -> ActionIntent:
        """
        Normalize natural language SRE action descriptions into structured ActionIntent.
        Extracts polarity, category, target resource, direction of change, and operational risk.
        """
        t = action_text.lower().strip()

        # 1. Action Polarity: Detect negation and avoidance
        negation_markers = [
            "do not",
            "don't",
            "dont",
            "avoid",
            "never",
            "refrain",
            "prevent",
            "should not",
            "must not",
            "prohibit",
            "stop",
        ]
        is_negated = any(re.search(rf"\b{re.escape(neg)}\b", t) for neg in negation_markers)
        polarity: Literal["POSITIVE", "NEGATIVE", "NEGATED"] = "NEGATED" if is_negated else "POSITIVE"

        # 2. Resource Type & Target Resource
        resource_type: Literal["POD", "WORKER", "CACHE", "DATABASE", "NETWORK", "CONFIGURATION", "GENERIC"] = "GENERIC"
        target_resource = ""

        if any(w in t for w in ["redis", "cache", "memcached", "keys", "key"]):
            resource_type = "CACHE"
            target_resource = "redis_cache"
        elif any(
            w in t
            for w in [
                "max_connections",
                "connection pool",
                "pool size",
                "pool capacity",
                "postgres pool",
                "db pool",
            ]
        ):
            resource_type = "DATABASE"
            target_resource = "database_connection_pool"
        elif any(w in t for w in ["postgres", "postgresql", "mysql", "database", "table", "schema", "pg_stat"]):
            resource_type = "DATABASE"
            target_resource = "relational_database"
        elif any(
            w in t
            for w in [
                "worker",
                "consumer",
                "replica",
                "replicas",
                "pod",
                "pods",
                "instance",
                "instances",
                "hpa",
            ]
        ):
            resource_type = "POD"
            target_resource = "application_instances"
        elif any(w in t for w in ["retry", "retries", "backoff", "dns", "coredns", "network", "socket", "ingress"]):
            resource_type = "NETWORK"
            target_resource = "network_client"
        elif any(w in t for w in ["helm", "config", "vault", "env", "secret"]):
            resource_type = "CONFIGURATION"
            target_resource = "configuration"

        # 3. Direction of Change
        direction: Literal["INCREASE", "DECREASE", "RESET", "RESTART", "PURGE", "PRESERVE", "NO_CHANGE", "UNKNOWN"] = (
            "UNKNOWN"
        )

        mag_from_to = re.search(r"\bfrom\s+(\d+)\s+to\s+(\d+)\b", t)

        if is_negated:
            direction = "NO_CHANGE"
        elif mag_from_to and int(mag_from_to.group(2)) < int(mag_from_to.group(1)):
            direction = "DECREASE"
        elif mag_from_to and int(mag_from_to.group(2)) > int(mag_from_to.group(1)):
            direction = "INCREASE"
        elif _match_term(
            [
                "flush",
                "flushed",
                "flushing",
                "flushall",
                "flushdb",
                "purge",
                "purged",
                "purging",
                "clear",
                "cleared",
                "clearing",
                "wipe",
                "wiped",
                "wiping",
                "evict",
                "evicted",
                "evicting",
            ],
            t,
        ):
            direction = "PURGE"
        elif _match_term(
            [
                "restart",
                "restarted",
                "restarting",
                "reboot",
                "rebooted",
                "rebooting",
                "rollout restart",
                "redeploy",
                "redeployed",
                "redeploying",
            ],
            t,
        ):
            direction = "RESTART"
        elif _match_term(
            [
                "reset",
                "revert",
                "reverted",
                "rollback",
            ],
            t,
        ):
            direction = "RESET"
        elif _match_term(
            [
                "preserve",
                "maintain",
                "keep",
                "freeze",
            ],
            t,
        ):
            direction = "PRESERVE"
        elif _match_term(
            [
                "scale down",
                "scale in",
                "decrease",
                "decreased",
                "decreasing",
                "reduce",
                "reduced",
                "reducing",
                "shrink",
                "lower",
                "drop",
                "cut",
                "slash",
            ],
            t,
        ):
            direction = "DECREASE"
        elif _match_term(
            [
                "scale up",
                "scale out",
                "scaled up",
                "scaled out",
                "scaling up",
                "scaling out",
                "scale",
                "scaled",
                "scaling",
                "increase",
                "increased",
                "increasing",
                "add",
                "added",
                "adding",
                "boost",
                "boosted",
                "boosting",
                "expand",
                "expanded",
                "expanding",
                "raise",
                "raised",
                "raising",
                "grow",
                "growing",
                "multiply",
                "aggressive",
                "aggressively",
            ],
            t,
        ):
            direction = "INCREASE"

        # 4. Action Category Assignment
        category = "UNKNOWN"
        if resource_type == "CACHE" and (
            direction in ("PURGE", "RESET")
            or _match_term(
                ["flush", "flushed", "flushing", "purge", "purged", "clear", "cleared", "evict", "evicted"],
                t,
            )
        ):
            category = "CACHE_FLUSH"
        elif target_resource == "database_connection_pool" and direction == "INCREASE":
            category = "POOL_EXPANSION_OVERCOMMIT"
        elif resource_type in ("POD", "WORKER") and (
            direction in ("INCREASE", "DECREASE")
            or _match_term(
                [
                    "scale",
                    "scaled",
                    "scaling",
                    "replica",
                    "replicas",
                    "instance",
                    "instances",
                    "pod",
                    "pods",
                    "hpa",
                ],
                t,
            )
        ):
            category = "HORIZONTAL_SCALE"
        elif target_resource == "network_client" or _match_term(["retry", "retries", "backoff"], t):
            if direction == "INCREASE" or _match_term(
                ["aggressive", "aggressively", "loop", "loops", "storm", "short", "shorter"], t
            ):
                category = "RETRY_AGGRESSIVE"
            else:
                category = "RETRY_TUNING"
        elif direction == "RESTART":
            category = "RESTART_PODS"
        elif _match_term(["inspect", "check", "monitor", "view", "verify", "select"], t):
            category = "DIAGNOSTIC_INSPECTION"

        # 5. Extract magnitude if available
        mag_match = re.search(
            r"\b(?:from\s+(\d+)\s+to\s+(\d+)|\b(\d+)\s*(?:replicas|pods|instances|retries|connections))\b",
            t,
        )
        magnitude = mag_match.group(0) if mag_match else None

        # 6. Reversibility & Blast Radius
        reversibility: Literal["Fully Reversible", "Partially Reversible", "Irreversible"] = "Fully Reversible"
        blast_radius: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
        if category == "CACHE_FLUSH":
            reversibility = "Partially Reversible"
            blast_radius = "HIGH"
        elif "drop table" in t or "delete" in t:
            reversibility = "Irreversible"
            blast_radius = "CRITICAL"
        elif category == "DIAGNOSTIC_INSPECTION":
            reversibility = "Fully Reversible"
            blast_radius = "LOW"

        return ActionIntent(
            raw_description=action_text,
            action_verb=t.split()[0] if t else "",
            action_polarity=polarity,
            operation_category=category,
            target_resource=target_resource,
            resource_type=resource_type,
            target_service=service,
            direction_of_change=direction,
            magnitude_or_value=magnitude,
            reversibility=reversibility,
            potential_blast_radius=blast_radius,
            requires_human_approval=(blast_radius in ("HIGH", "CRITICAL")),
        )

    @classmethod
    def detect_action_cluster(cls, text: str) -> str | None:
        """Detect operational semantic intent category for an action description."""
        intent = cls.normalize_action_intent(text)
        return intent.operation_category if intent.operation_category != "UNKNOWN" else None

    @classmethod
    def compare_action_semantics(
        cls,
        proposed_action: str | ActionIntent,
        historical_action: str | ActionIntent,
        current_symptoms: list[str] | None = None,
        current_service: str | None = None,
        historical_service: str | None = None,
    ) -> ActionEquivalenceEvaluation:
        """
        Compare semantic intent of a proposed remediation step against a historical action.
        Exposes explicit relations: EXACT_EQUIVALENT, SEMANTIC_EQUIVALENT, OPPOSITE_ACTION,
        NEGATED_ACTION, RELATED_BUT_DISTINCT, or UNKNOWN.
        """
        intent_prop = (
            cls.normalize_action_intent(proposed_action, current_service)
            if isinstance(proposed_action, str)
            else proposed_action
        )
        intent_hist = (
            cls.normalize_action_intent(historical_action, historical_service)
            if isinstance(historical_action, str)
            else historical_action
        )

        matched_fields = []
        conflicting_fields = []

        # 1. Check Action Polarity
        if intent_prop.action_polarity != intent_hist.action_polarity:
            conflicting_fields.append("action_polarity")
            explanation = (
                f"Actions have opposing operational polarities: '{intent_prop.raw_description}' is "
                f"{intent_prop.action_polarity} whereas historical '{intent_hist.raw_description}' is {intent_hist.action_polarity}. "
                "Negated actions must not be conflated with executable operations."
            )
            return ActionEquivalenceEvaluation(
                semantic_relation="NEGATED_ACTION",
                is_equivalent=False,
                action_category=intent_prop.operation_category,
                historical_action=intent_hist.raw_description,
                proposed_action=intent_prop.raw_description,
                matched_fields=[],
                conflicting_fields=conflicting_fields,
                similarity_score=0.20,
                confidence=0.90,
                explanation=explanation,
                is_applicable_under_current_conditions=True,
                applicability_decision="SAFE_UNDER_CONDITIONS",
            )

        matched_fields.append("action_polarity")

        # 2. Check Direction of Change
        if (
            intent_prop.direction_of_change != "UNKNOWN"
            and intent_hist.direction_of_change != "UNKNOWN"
            and intent_prop.direction_of_change != intent_hist.direction_of_change
        ):
            # Check opposite directions: e.g. INCREASE vs DECREASE
            if {intent_prop.direction_of_change, intent_hist.direction_of_change} == {"INCREASE", "DECREASE"}:
                conflicting_fields.append("direction_of_change")
                explanation = (
                    f"Actions operate in opposite directions: '{intent_prop.raw_description}' is "
                    f"{intent_prop.direction_of_change} whereas historical action is {intent_hist.direction_of_change}."
                )
                return ActionEquivalenceEvaluation(
                    semantic_relation="OPPOSITE_ACTION",
                    is_equivalent=False,
                    action_category=intent_prop.operation_category,
                    historical_action=intent_hist.raw_description,
                    proposed_action=intent_prop.raw_description,
                    matched_fields=matched_fields,
                    conflicting_fields=conflicting_fields,
                    similarity_score=0.35,
                    confidence=0.88,
                    explanation=explanation,
                    is_applicable_under_current_conditions=True,
                    applicability_decision="SAFE_UNDER_CONDITIONS",
                )

        if (
            intent_prop.direction_of_change == intent_hist.direction_of_change
            and intent_prop.direction_of_change != "UNKNOWN"
        ):
            matched_fields.append("direction_of_change")

        # 3. Check Target Resource & Resource Type
        if intent_prop.resource_type != "GENERIC" and intent_hist.resource_type != "GENERIC":
            if intent_prop.resource_type != intent_hist.resource_type:
                conflicting_fields.append("resource_type")
                explanation = (
                    f"Actions target fundamentally distinct architectural layers: "
                    f"'{intent_prop.raw_description}' ({intent_prop.resource_type}) vs historical "
                    f"'{intent_hist.raw_description}' ({intent_hist.resource_type})."
                )
                return ActionEquivalenceEvaluation(
                    semantic_relation="RELATED_BUT_DISTINCT",
                    is_equivalent=False,
                    action_category=f"{intent_prop.operation_category}_VS_{intent_hist.operation_category}",
                    historical_action=intent_hist.raw_description,
                    proposed_action=intent_prop.raw_description,
                    matched_fields=matched_fields,
                    conflicting_fields=conflicting_fields,
                    similarity_score=0.25,
                    confidence=0.85,
                    explanation=explanation,
                    is_applicable_under_current_conditions=True,
                    applicability_decision="SAFE_UNDER_CONDITIONS",
                )
            else:
                matched_fields.append("resource_type")

        # 4. Check Operation Category
        if (
            intent_prop.operation_category != "UNKNOWN"
            and intent_prop.operation_category == intent_hist.operation_category
        ):
            matched_fields.append("operation_category")

        # 5. Determine Semantic Relation & Equivalence
        is_exact = intent_prop.raw_description.lower().strip() == intent_hist.raw_description.lower().strip()
        is_semantic = (
            "operation_category" in matched_fields
            and "action_polarity" in matched_fields
            and ("direction_of_change" in matched_fields or intent_prop.direction_of_change == "UNKNOWN")
            and len(conflicting_fields) == 0
        )

        tokens_p = {w for w in re.findall(r"[a-z0-9_\-]+", intent_prop.raw_description.lower()) if len(w) > 3}
        tokens_h = {w for w in re.findall(r"[a-z0-9_\-]+", intent_hist.raw_description.lower()) if len(w) > 3}
        token_sim = (
            (len(tokens_p.intersection(tokens_h)) / max(1, len(tokens_p.union(tokens_h))))
            if tokens_p and tokens_h
            else 0.0
        )

        if is_exact:
            relation = "EXACT_EQUIVALENT"
            is_equiv = True
            sim_score = 1.0
            conf = 0.98
            explanation = f"Proposed action identically matches historical action: '{intent_hist.raw_description}'."
        elif is_semantic:
            relation = "SEMANTIC_EQUIVALENT"
            is_equiv = True
            sim_score = round(0.75 + (0.20 * token_sim), 2)
            conf = 0.90
            cluster_info = ACTION_SEMANTIC_CLUSTERS.get(intent_prop.operation_category, {})
            risk_desc = cluster_info.get("failure_explanation", "Shares operational intent and failure mechanics.")
            explanation = (
                f"Proposed action '{intent_prop.raw_description}' shares semantic operational intent "
                f"({intent_prop.operation_category}, direction: {intent_prop.direction_of_change}) "
                f"with historical action '{intent_hist.raw_description}': {risk_desc}"
            )
        elif token_sim >= 0.5:
            relation = "SEMANTIC_EQUIVALENT"
            is_equiv = True
            sim_score = round(token_sim, 2)
            conf = 0.75
            explanation = f"High token alignment ({token_sim:.0%}) between proposed and historical action."
        else:
            relation = "RELATED_BUT_DISTINCT" if matched_fields else "UNKNOWN"
            is_equiv = False
            sim_score = round(token_sim, 2)
            conf = 0.80
            explanation = "Actions belong to distinct operational categories or lack sufficient context."

        # 6. Condition Analysis & Applicability
        is_applicable = True
        app_decision: Literal[
            "INAPPLICABLE",
            "POTENTIALLY_HARMFUL",
            "SAFE_UNDER_CONDITIONS",
            "INSUFFICIENT_TELEMETRY",
            "REQUIRES_HUMAN_INVESTIGATION",
        ] = "SAFE_UNDER_CONDITIONS"
        symptoms_str = " ".join(current_symptoms or []).lower()

        cluster_info = ACTION_SEMANTIC_CLUSTERS.get(intent_prop.operation_category)
        if cluster_info:
            harmful = cluster_info.get("harmful_symptoms", [])
            matched_harmful = [h for h in harmful if h in symptoms_str]
            if matched_harmful:
                is_applicable = False
                app_decision = "POTENTIALLY_HARMFUL"
                explanation += f" WARNING: Inapplicable under active symptoms ({', '.join(matched_harmful)})."

        return ActionEquivalenceEvaluation(
            semantic_relation=relation,
            is_equivalent=is_equiv,
            action_category=intent_prop.operation_category,
            historical_action=intent_hist.raw_description,
            proposed_action=intent_prop.raw_description,
            matched_fields=matched_fields,
            conflicting_fields=conflicting_fields,
            similarity_score=sim_score,
            confidence=conf,
            explanation=explanation,
            is_applicable_under_current_conditions=is_applicable,
            applicability_decision=app_decision,
        )

    def evaluate_action_against_history(
        self,
        proposed_action: str,
        current_symptoms: list[str] | None,
        current_service: str | None,
        recalled_memories: list[RecalledMemoryItem],
    ) -> list[ActionEquivalenceEvaluation]:
        """
        Evaluate a proposed action against historical lessons recalled from Hindsight.
        Determines semantic equivalence, service context relevance, condition applicability, and safe alternatives.
        Differentiates FAILED from SUCCESSFUL fixes to prevent false negative alerts.
        """
        evaluations: list[ActionEquivalenceEvaluation] = []

        # 1. Evaluate against known failed mitigations to avoid
        failed_warnings = self.extract_failed_approaches(recalled_memories)
        for warning in failed_warnings:
            hist_fix = warning.approach
            eval_res = self.compare_action_semantics(
                proposed_action=proposed_action,
                historical_action=hist_fix,
                current_symptoms=current_symptoms,
                current_service=current_service,
            )

            # Service relevance reasoning
            hist_src = warning.historical_source_incident
            service_note = ""
            if current_service:
                if current_service.lower() in warning.why_failed.lower() or current_service.lower() in hist_src.lower():
                    service_note = f" (Direct service match for {current_service})"
                else:
                    service_note = f" (Cross-service architectural precedent from {hist_src})"

            if eval_res.is_equivalent:
                eval_res.historical_outcome = "FAILED"
                eval_res.historical_provenance = hist_src
                eval_res.explanation += service_note
                eval_res.suggested_alternative = (
                    warning.suggested_alternative or "Review verified effective resolution in memory."
                )
                evaluations.append(eval_res)

        # 2. Evaluate against verified successful resolutions
        successful_resolutions = self.extract_successful_resolutions(recalled_memories)
        for s_res in successful_resolutions:
            eval_succ = self.compare_action_semantics(
                proposed_action=proposed_action,
                historical_action=s_res["resolution"],
                current_symptoms=current_symptoms,
                current_service=current_service,
            )
            if eval_succ.is_equivalent:
                eval_succ.historical_outcome = "SUCCESSFUL"
                eval_succ.historical_provenance = s_res["source"]
                eval_succ.is_applicable_under_current_conditions = True
                eval_succ.applicability_decision = "SAFE_UNDER_CONDITIONS"
                eval_succ.explanation = (
                    f"Action aligns with verified effective operational resolution from {s_res['source']}: "
                    f"'{s_res['resolution']}'."
                )
                evaluations.append(eval_succ)

        return evaluations

    def detect_contradictions(
        self,
        proposed_action: str,
        recalled_memories: list[RecalledMemoryItem],
        current_symptoms: list[str] | None = None,
        current_service: str | None = None,
    ) -> list[str]:
        """
        Check if a proposed action contradicts operational memories.
        Uses semantic equivalence matching and harmful condition detection.
        Respects negation: negating a harmful action complies with policy and is NOT a contradiction.
        """
        contradictions = []
        prop_intent = self.normalize_action_intent(proposed_action, current_service)

        # If the proposed action is explicitly negated (e.g. "Do not flush Redis"), it does not repeat a failed action!
        if prop_intent.action_polarity == "NEGATED":
            return []

        failed_warnings = self.extract_failed_approaches(recalled_memories)
        for w in failed_warnings:
            eval_res = self.compare_action_semantics(
                proposed_action=prop_intent,
                historical_action=w.approach,
                current_symptoms=current_symptoms,
                current_service=current_service,
            )
            if eval_res.is_equivalent:
                src = w.historical_source_incident
                msg = (
                    f"Action '{proposed_action}' matches previously failed mitigation from {src}: '{w.approach}' "
                    f"(Relation: {eval_res.semantic_relation}, Category: {eval_res.action_category})."
                )
                if not eval_res.is_applicable_under_current_conditions:
                    msg += " WARNING: Exacerbates active system degradation under current symptoms."
                contradictions.append(msg)
            elif eval_res.semantic_relation == "RELATED_BUT_DISTINCT":
                continue
            else:
                # Token fallback
                approach_words = [w_tok for w_tok in w.approach.lower().split() if len(w_tok) > 4]
                if approach_words and all(tok in proposed_action.lower() for tok in approach_words[:2]):
                    contradictions.append(
                        f"Action '{proposed_action}' directly contradicts historical postmortem {w.historical_source_incident}: '{w.approach}'"
                    )

        return contradictions

    def reflect_patterns(
        self,
        query: str,
        budget: str = "mid",
        context: str | None = None,
        bank_id: str | None = None,
    ) -> str | None:
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


_memory_manager_instance: MemoryManager | None = None


def get_memory_manager() -> MemoryManager:
    """Singleton getter for MemoryManager."""
    global _memory_manager_instance
    if _memory_manager_instance is None:
        _memory_manager_instance = MemoryManager()
    return _memory_manager_instance
