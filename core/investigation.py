"""
Investigation Engine for OPSRECALL.
Coordinates the end-to-end incident investigation workflow:
1. Incident input validation and telemetry sanitization.
2. Hindsight memory recall (when enabled) with multi-factor ranking.
3. LLM reasoning and evidence synthesis.
4. Structured hypothesis and remediation generation.
5. Extraction of previously failed fixes & contradiction detection.
6. Execution of side-by-side Memory ON vs. Memory OFF comparisons.
7. Local audit logging.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Literal

from core.incident_engine import get_incident_engine
from core.llm_engine import LLMEngine, get_llm_engine
from core.memory_manager import MemoryManager, get_memory_manager
from core.validators import (
    ActionEquivalenceEvaluation,
    ActionRecommendation,
    FailedApproachWarning,
    Hypothesis,
    InvestigationResult,
    RecalledMemoryItem,
    StructuredRetrievalResult,
)
from database.db import DatabaseManager, get_db

logger = logging.getLogger("opsrecall.investigation")


class InvestigationEngine:
    """Orchestrates incident investigations with or without Hindsight memory."""

    def __init__(
        self,
        memory_manager: MemoryManager | None = None,
        llm_engine: LLMEngine | None = None,
        db: DatabaseManager | None = None,
    ):
        self.memory_manager = memory_manager or get_memory_manager()
        self.llm_engine = llm_engine or get_llm_engine()
        self.db = db or get_db()
        self.incident_engine = get_incident_engine()

    def investigate(
        self,
        incident_data: dict[str, Any],
        memory_mode: str = "MEMORY_ENABLED",
    ) -> InvestigationResult:
        """
        Execute an incident investigation.

        Args:
            incident_data: Dictionary representing current incident symptoms and context.
            memory_mode: "MEMORY_ENABLED" or "MEMORY_DISABLED".
        """
        start_time = time.time()
        investigation_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
        inc_id = incident_data.get("incident_id") or incident_data.get("case_id") or "CURRENT"
        service = incident_data.get("affected_service", "unknown-service")
        symptoms = incident_data.get("symptoms", [])
        error_logs = incident_data.get("error_logs", [])
        deployment_change = incident_data.get("deployment_or_change") or incident_data.get("recent_deployment")

        recalled_memories: list[RecalledMemoryItem] = []
        structured_retrievals: list[StructuredRetrievalResult] = []
        retrieval_mode_label = "DISABLED"

        # 1. Memory Retrieval step
        if memory_mode == "MEMORY_ENABLED":
            if self.memory_manager.client.is_configured:
                query = self.memory_manager.build_recall_query(
                    service=service,
                    symptoms=symptoms,
                    error_logs=error_logs,
                    deployment_change=deployment_change,
                )
                recalled_memories = self.memory_manager.recall_memories(
                    query=query,
                    tags=[service] if service else None,
                )
                retrieval_mode_label = "LIVE_HINDSIGHT"

            # If Hindsight is in offline preview mode (not configured) but memory is enabled,
            # retrieve from local simulated incidents with clear simulation tagging
            if not recalled_memories and not self.memory_manager.client.is_configured:
                recalled_memories = self._get_offline_preview_memories(
                    service=service,
                    symptoms=symptoms,
                    error_logs=error_logs,
                    deployment_change=deployment_change,
                )
                retrieval_mode_label = "OFFLINE_SIMULATION"

            # Rank and synthesize structured retrieval explanations
            if recalled_memories:
                structured_retrievals = self.memory_manager.rank_and_structure_retrievals(
                    recalled_memories=recalled_memories,
                    current_service=service,
                    current_symptoms=symptoms,
                    current_errors=error_logs,
                    current_change=deployment_change,
                )

        # 2. LLM Reasoning step
        llm_output = self.llm_engine.generate_investigation(
            incident_data=incident_data,
            recalled_memories=recalled_memories,
            memory_mode=memory_mode,
        )

        # 3. Parse hypotheses
        raw_hypotheses = llm_output.get("hypotheses", [])
        hypotheses: list[Hypothesis] = []
        for idx, h in enumerate(raw_hypotheses, 1):
            if isinstance(h, dict):
                h_likelihood = h.get("likelihood", "Medium")
                default_prob = 0.85 if h_likelihood == "High" else (0.55 if h_likelihood == "Medium" else 0.25)
                hypotheses.append(
                    Hypothesis(
                        rank=h.get("rank", idx),
                        hypothesis=h.get("hypothesis", ""),
                        supporting_evidence=h.get("supporting_evidence", []),
                        contradictory_evidence=h.get("contradictory_evidence", []),
                        likelihood=h_likelihood,
                        probability=float(h.get("probability", default_prob)),
                        historical_precedent=h.get("historical_precedent"),
                        missing_evidence=h.get("missing_evidence", []),
                        validation_procedure=h.get("validation_procedure"),
                    )
                )

        # 4. Parse historical references and failed approaches
        hist_refs = llm_output.get("historical_incidents_referenced", [])
        if not hist_refs and memory_mode == "MEMORY_ENABLED":
            for sr in structured_retrievals:
                if sr.incident_id and sr.incident_id not in hist_refs and (sr.relevance_score or 0.0) > 0.3:
                    hist_refs.append(sr.incident_id)

        failed_approaches: list[FailedApproachWarning] = []
        for f in llm_output.get("previous_failed_approaches", []):
            if isinstance(f, dict):
                failed_approaches.append(
                    FailedApproachWarning(
                        approach=f.get("approach", ""),
                        why_failed=f.get("why_failed", ""),
                        historical_source_incident=f.get("historical_source_incident", "Historical Record"),
                        suggested_alternative=f.get("suggested_alternative"),
                    )
                )

        # Merge any failed approaches directly extracted by memory manager
        if memory_mode == "MEMORY_ENABLED" and recalled_memories:
            extracted_warnings = self.memory_manager.extract_failed_approaches(recalled_memories)
            existing_approaches = {fa.approach.lower() for fa in failed_approaches}
            for ew in extracted_warnings:
                if ew.approach.lower() not in existing_approaches:
                    failed_approaches.append(ew)
                    existing_approaches.add(ew.approach.lower())

        # 5. Parse recommendations & check for safety and contradictions
        diagnostic_actions: list[ActionRecommendation] = []
        for d in llm_output.get("recommended_diagnostic_actions", []):
            if isinstance(d, dict):
                diagnostic_actions.append(
                    ActionRecommendation(
                        step_number=d.get("step_number", len(diagnostic_actions) + 1),
                        action_type=d.get("action_type", "Diagnostic"),
                        safety_classification=d.get("safety_classification", "Diagnostic"),
                        description=d.get("description", ""),
                        rationale=d.get("rationale", ""),
                        expected_impact=d.get("expected_impact", "Isolate root cause"),
                        preconditions=d.get("preconditions", []),
                        verification_steps=d.get("verification_steps", []),
                        potential_risks=d.get("potential_risks", "None - read-only query."),
                        commands_or_checks=d.get("commands_or_checks", []),
                        requires_human_approval=d.get("requires_human_approval", True),
                        is_destructive=d.get("is_destructive", False),
                        reversibility=d.get("reversibility", "Fully Reversible"),
                    )
                )

        remediation_steps: list[ActionRecommendation] = []
        for r in llm_output.get("recommended_remediation_steps", []):
            if isinstance(r, dict):
                is_dest = r.get("is_destructive", False)
                safety_cls = r.get("safety_classification", "Destructive" if is_dest else "Reversible")
                remediation_steps.append(
                    ActionRecommendation(
                        step_number=r.get("step_number", len(remediation_steps) + 1),
                        action_type=r.get("action_type", "Remediation"),
                        safety_classification=safety_cls,
                        description=r.get("description", ""),
                        rationale=r.get("rationale", ""),
                        expected_impact=r.get("expected_impact", "Restore service health"),
                        preconditions=r.get("preconditions", []),
                        verification_steps=r.get("verification_steps", []),
                        potential_risks=r.get("potential_risks", "Standard deployment restart risk."),
                        commands_or_checks=r.get("commands_or_checks", []),
                        requires_human_approval=r.get("requires_human_approval", True),
                        is_destructive=is_dest,
                        reversibility=r.get("reversibility", "Fully Reversible"),
                    )
                )

        # Check for contradictions and semantic action equivalence across all recommendations
        contradictions_detected: list[str] = []
        action_evaluations: list[ActionEquivalenceEvaluation] = []
        if memory_mode == "MEMORY_ENABLED" and recalled_memories:
            for rem in remediation_steps + diagnostic_actions:
                conflicts = self.memory_manager.detect_contradictions(
                    rem.description, recalled_memories, current_symptoms=symptoms, current_service=service
                )
                contradictions_detected.extend(conflicts)
                evals = self.memory_manager.evaluate_action_against_history(
                    rem.description, symptoms, service, recalled_memories
                )
                action_evaluations.extend(evals)

        elapsed = round(time.time() - start_time, 3)

        c_level = llm_output.get("confidence_level", "Medium")
        num_conf = llm_output.get("numerical_confidence")
        if num_conf is None or not (0.0 <= float(num_conf) <= 1.0):
            num_conf = 0.88 if c_level == "High" else (0.62 if c_level == "Medium" else 0.35)
        else:
            num_conf = float(num_conf)

        # Precise provenance determination
        is_live_mem = bool(self.memory_manager.client.is_configured)
        is_live_llm = bool(getattr(self.llm_engine, "client", None) is not None)
        is_simulated = not (is_live_mem and is_live_llm)

        mem_conn_state: Literal["LIVE_CONNECTED", "OFFLINE_PREVIEW", "DISABLED", "CONNECTION_ERROR"] = (
            "DISABLED" if memory_mode == "MEMORY_DISABLED" else ("LIVE_CONNECTED" if is_live_mem else "OFFLINE_PREVIEW")
        )
        model_conn_state: Literal["LIVE_CONNECTED", "OFFLINE_RULE_BASED", "FALLBACK_CASCADE", "ERROR"] = (
            "LIVE_CONNECTED" if is_live_llm else "OFFLINE_RULE_BASED"
        )
        model_id = (
            llm_output.get("llm_model", "groq:openai/gpt-oss-120b") if is_live_llm else "deterministic-offline-reasoner"
        )
        ranked_candidates = self.memory_manager.to_canonical_candidates(structured_retrievals)

        result = InvestigationResult(
            investigation_id=investigation_id,
            incident_id=inc_id,
            mode=memory_mode,
            retrieval_mode_label=retrieval_mode_label,
            executive_summary=llm_output.get("executive_summary", "Operational investigation completed."),
            hypotheses=hypotheses,
            evidence_summary=symptoms + error_logs[:2],
            recalled_memories=recalled_memories,
            structured_retrievals=structured_retrievals,
            ranked_candidates=ranked_candidates,
            historical_incidents_referenced=hist_refs,
            previous_failed_approaches=failed_approaches,
            memory_contradictions_detected=contradictions_detected,
            action_evaluations=action_evaluations,
            recommended_diagnostic_actions=diagnostic_actions,
            recommended_remediation_steps=remediation_steps,
            confidence_level=c_level,
            confidence_explanation=llm_output.get("confidence_explanation", ""),
            numerical_confidence=num_conf,
            missing_information=llm_output.get("missing_information", []),
            requires_human_intervention=True,
            memory_provider="Hindsight Cloud",
            memory_connection_state=mem_conn_state,
            model_provider="Groq",
            model_connection_state=model_conn_state,
            fallback_used=not is_live_llm,
            is_simulated=is_simulated,
            live_verification_occurred=bool(is_live_mem and is_live_llm),
            execution_time_seconds=elapsed,
            llm_model=model_id,
        )

        # 6. Save audit record to SQLite
        try:
            self.db.save_investigation(result)
        except Exception as e:
            logger.warning(f"Could not save investigation to SQLite: {e}")

        return result

    def run_comparison(
        self,
        incident_data: dict[str, Any],
    ) -> tuple[InvestigationResult, InvestigationResult]:
        """
        Execute identical incident investigation under both modes for side-by-side comparison:
        1. WITHOUT HINDSIGHT (Memory Disabled)
        2. WITH HINDSIGHT (Memory Enabled)
        """
        res_disabled = self.investigate(incident_data, memory_mode="MEMORY_DISABLED")
        res_enabled = self.investigate(incident_data, memory_mode="MEMORY_ENABLED")
        return res_disabled, res_enabled

    def _get_offline_preview_memories(
        self,
        service: str,
        symptoms: list[str] | None = None,
        error_logs: list[str] | None = None,
        deployment_change: str | None = None,
    ) -> list[RecalledMemoryItem]:
        """
        Provides simulated recall items from data/incidents.json strictly when
        Hindsight is unconfigured.
        Emulates Hindsight TEMPR by requiring semantic symptom and failure pattern
        alignment, rather than matching solely on service name.
        """
        incidents = self.incident_engine.get_all_incidents()
        matched: list[RecalledMemoryItem] = []

        sym_list = symptoms or []
        err_list = error_logs or []

        query_text = (" ".join(sym_list) + " " + " ".join(err_list) + " " + str(deployment_change or "")).lower()

        for inc in incidents:
            if inc.affected_service == service:
                inc_text = (
                    " ".join(inc.symptoms)
                    + " "
                    + " ".join(inc.error_logs)
                    + " "
                    + str(inc.actual_verified_root_cause or "")
                    + " "
                    + str(inc.deployment_or_change or "")
                ).lower()

                # Semantic alignment verification: Ensure the problem domain actually matches
                has_semantic_alignment = False

                if "pool" in query_text and "pool" in inc_text:
                    # Distinguish connection pool from table lock and cross-rack packet drop
                    if (
                        "lock" not in query_text
                        and "accessexclusivelock" not in query_text
                        and "cross-rack" not in query_text
                        and "az-east" not in query_text
                        and "sporadic" not in query_text
                    ):
                        has_semantic_alignment = True
                elif ("concurrency" in query_text or "consumer" in query_text or "queue" in query_text) and (
                    "concurrency" in inc_text or "consumer" in inc_text or "replicas" in inc_text
                ):
                    # Distinguish worker capacity from CPU-bound PDF rendering
                    if "pdf" not in query_text and "invoice" not in query_text:
                        has_semantic_alignment = True
                elif ("cert" in query_text or "tls" in query_text or "ssl" in query_text) and (
                    "cert" in inc_text or "tls" in inc_text or "ssl" in inc_text
                ):
                    # Distinguish TLS cert from heap memory leak in payment-gateway
                    if "jackson" not in query_text and "heap" not in query_text:
                        has_semantic_alignment = True
                elif ("stampede" in query_text or "redis" in query_text or "ttl" in query_text) and (
                    "stampede" in inc_text or "redis" in inc_text
                ):
                    # Distinguish cache stampede from node memory pressure and eviction thrashing
                    if (
                        "nodememorypressure" not in query_text
                        and "gin" not in query_text
                        and "eviction" not in query_text
                        and "volatile-lru" not in query_text
                    ):
                        has_semantic_alignment = True
                elif (
                    "partner" in query_text
                    or "paycorp" in query_text
                    or "circuit" in query_text
                    or "upstream" in query_text
                ) and ("partner" in inc_text or "paycorp" in inc_text or "circuit" in inc_text):
                    # Distinguish partner latency from retry storm amplification
                    if "retry" not in query_text and "amplification" not in query_text:
                        has_semantic_alignment = True

                if has_semantic_alignment:
                    formatted_text = self.memory_manager.format_incident_for_retention(inc)
                    matched.append(
                        RecalledMemoryItem(
                            memory_id=f"preview-{inc.incident_id.lower()}",
                            text=formatted_text,
                            memory_type="experience",
                            document_id=inc.incident_id,
                            tags=[inc.affected_service, inc.severity, "offline-preview"],
                            metadata={
                                "incident_id": inc.incident_id,
                                "mode": "OFFLINE_PREVIEW",
                                "service": inc.affected_service,
                                "is_verified": "True" if inc.actual_verified_root_cause else "False",
                            },
                            relevance_score=0.92,
                            source_incident_id=inc.incident_id,
                            timestamp=inc.incident_timestamp,
                            is_verified=bool(inc.actual_verified_root_cause),
                        )
                    )

        return matched


_investigation_engine_instance: InvestigationEngine | None = None


def get_investigation_engine() -> InvestigationEngine:
    """Singleton getter for InvestigationEngine."""
    global _investigation_engine_instance
    if _investigation_engine_instance is None:
        _investigation_engine_instance = InvestigationEngine()
    return _investigation_engine_instance
