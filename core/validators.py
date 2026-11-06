"""
Data models and validation schemas for OPSRECALL.
Defines strongly-typed Pydantic schemas for incidents, investigations,
recalled memories, evaluations, and human resolution feedback.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


def current_iso_time() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


class Incident(BaseModel):
    """Schema for a simulated or live incident."""

    incident_id: str = Field(..., description="Unique incident identifier, e.g. INC-001")
    incident_title: str = Field(..., description="Short incident summary title")
    affected_service: str = Field(..., description="Name of the impacted service")
    incident_timestamp: str = Field(default_factory=current_iso_time)
    severity: Literal["SEV-1", "SEV-2", "SEV-3", "SEV-4"] = Field(..., description="Severity level")
    symptoms: List[str] = Field(default_factory=list, description="Observed operational symptoms")
    error_logs: List[str] = Field(default_factory=list, description="Error log excerpts")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Key operational metrics")
    deployment_id: Optional[str] = Field(default=None, description="Recent deployment identifier")
    deployment_or_change: Optional[str] = Field(default=None, description="Recent code or config change")
    
    # Crucial Distinction: Suspected Cause vs Human-Verified Root Cause
    suspected_cause: Optional[str] = Field(default=None, description="Initial triage suspicion (UNVERIFIED)")
    actual_verified_root_cause: Optional[str] = Field(default=None, description="Confirmed root cause (VERIFIED)")
    is_verified: bool = Field(default=False, description="Whether root cause has been verified by an SRE")
    verified_by: Optional[str] = Field(default=None, description="Engineer or incident commander who verified")
    verified_at: Optional[str] = Field(default=None, description="Timestamp of human verification")

    diagnostic_actions_attempted: List[str] = Field(default_factory=list)
    failed_mitigation_attempts: List[str] = Field(default_factory=list, description="Ineffective or harmful actions")
    successful_mitigation: Optional[str] = Field(default=None, description="Immediate mitigation that stabilized service")
    resolution: Optional[str] = Field(default=None, description="Permanent root cause resolution")
    resolution_outcome: Optional[str] = Field(default=None)
    verification_evidence: Optional[str] = Field(default=None, description="Metrics or logs proving recovery")
    lessons_learned: Optional[str] = Field(default=None)
    data_type: str = Field(default="SIMULATED_INCIDENT", description="Explicit simulation label")
    content_hash: Optional[str] = Field(default=None, description="SHA-256 fingerprint for deduplication")

    def compute_content_hash(self) -> str:
        """Generate a deterministic SHA-256 hash of core incident characteristics."""
        norm_symptoms = sorted([s.strip().lower() for s in self.symptoms])
        norm_logs = sorted([e.strip().lower() for e in self.error_logs[:5]])
        raw = f"{self.affected_service.lower()}|{self.incident_title.lower()}|{'|'.join(norm_symptoms)}|{'|'.join(norm_logs)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class EvaluationCase(BaseModel):
    """
    Model-facing incident telemetry for reproducible evaluation scenarios.
    Strictly decoupled from evaluation ground-truth answer keys to guarantee zero leakage.
    """

    case_id: str
    case_title: str
    affected_service: str
    severity: Literal["SEV-1", "SEV-2", "SEV-3", "SEV-4"]
    symptoms: List[str] = Field(default_factory=list)
    error_logs: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    recent_deployment: Optional[str] = None
    configuration_changes: Optional[str] = None


class EvaluationGroundTruth(BaseModel):
    """
    Evaluator-only ground-truth answer keys and rubric labels.
    Never passed to the model or investigation engine.
    """

    case_id: str
    scenario_type: str = Field(default="recurrent_incident")
    ground_truth_root_cause: str
    expected_historical_match: Optional[str] = None
    unsuccessful_mitigations_to_avoid: List[str] = Field(default_factory=list)
    expected_optimal_first_action: Optional[str] = None
    is_distractor: bool = False
    requires_uncertainty: bool = False
    rubric_notes: str = ""
    domain_category: str = "infrastructure"


class RecalledMemoryItem(BaseModel):
    """A structured memory unit retrieved from Hindsight."""

    memory_id: str
    text: str
    memory_type: str = Field(default="experience", description="world, experience, or observation")
    document_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    relevance_score: Optional[float] = None
    source_incident_id: Optional[str] = None
    timestamp: Optional[str] = None
    is_verified: bool = False


class StructuredRetrievalResult(BaseModel):
    """
    Enhanced, context-aware retrieval result containing multi-factor ranking,
    evidence alignment, verification status, and transparent retrieval rationale.
    """

    incident_id: str
    title: str
    service: str
    why_retrieved: str
    matching_evidence: List[str] = Field(default_factory=list)
    relevance_score: Optional[float] = None
    ranking_factors: Dict[str, float] = Field(default_factory=dict)
    is_verified: bool = False
    verified_by: Optional[str] = None
    verified_root_cause: Optional[str] = None
    failed_mitigations_to_avoid: List[str] = Field(default_factory=list)
    effective_resolution: Optional[str] = None
    temporal_recency: Optional[str] = None
    memory_limitations: Optional[str] = None
    raw_memory: Optional[RecalledMemoryItem] = None


class Hypothesis(BaseModel):
    """A root-cause hypothesis with evidence grounding."""

    rank: int = Field(..., ge=1, le=5)
    hypothesis: str
    supporting_evidence: List[str] = Field(default_factory=list)
    likelihood: Literal["High", "Medium", "Low"] = "Medium"
    historical_precedent: Optional[str] = None


class ActionRecommendation(BaseModel):
    """Recommended diagnostic or remediation action."""

    step_number: int
    action_type: Literal["Diagnostic", "Remediation", "Verification"]
    description: str
    rationale: str
    potential_risks: str = "Low risk if followed according to SOP."
    commands_or_checks: List[str] = Field(default_factory=list)
    requires_human_approval: bool = True
    is_destructive: bool = False
    reversibility: Literal["Fully Reversible", "Partially Reversible", "Irreversible"] = "Fully Reversible"


class FailedApproachWarning(BaseModel):
    """Historical failed fix to avoid repeating."""

    approach: str
    why_failed: str
    historical_source_incident: str
    suggested_alternative: Optional[str] = None


class InvestigationResult(BaseModel):
    """Complete structured investigation report."""

    investigation_id: str
    incident_id: str
    mode: Literal["MEMORY_ENABLED", "MEMORY_DISABLED"]
    retrieval_mode_label: str = Field(default="LIVE_HINDSIGHT", description="LIVE_HINDSIGHT, OFFLINE_SIMULATION, or DISABLED")
    executive_summary: str
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    evidence_summary: List[str] = Field(default_factory=list)
    recalled_memories: List[RecalledMemoryItem] = Field(default_factory=list)
    structured_retrievals: List[StructuredRetrievalResult] = Field(default_factory=list)
    historical_incidents_referenced: List[str] = Field(default_factory=list)
    previous_failed_approaches: List[FailedApproachWarning] = Field(default_factory=list)
    memory_contradictions_detected: List[str] = Field(default_factory=list)
    recommended_diagnostic_actions: List[ActionRecommendation] = Field(default_factory=list)
    recommended_remediation_steps: List[ActionRecommendation] = Field(default_factory=list)
    confidence_level: Literal["High", "Medium", "Low"] = "Medium"
    confidence_explanation: str
    missing_information: List[str] = Field(default_factory=list)
    requires_human_intervention: bool = True
    is_simulated: bool = True
    execution_time_seconds: float = 0.0
    llm_model: str = ""
    created_at: str = Field(default_factory=current_iso_time)


class ResolutionFeedback(BaseModel):
    """Human-confirmed incident outcome for Hindsight retention."""

    incident_id: str
    verified_root_cause: str
    successful_resolution: str
    failed_approaches: List[str] = Field(default_factory=list)
    verification_evidence: str
    lessons_learned: str
    verified_by: str = "SRE On-Call Engineer"
    is_verified: bool = True
    status: Literal[
        "FEEDBACK_RECEIVED",
        "FEEDBACK_VALIDATED",
        "LOCAL_AUDIT_SAVED",
        "HINDSIGHT_RETENTION_ATTEMPTED",
        "HINDSIGHT_RETENTION_CONFIRMED",
        "MEMORY_RETRIEVABLE",
        "RETENTION_FAILED"
    ] = "FEEDBACK_RECEIVED"
    retained_to_hindsight: bool = False
    hindsight_operation_id: Optional[str] = None
    error_message: Optional[str] = None
    conflict_detected: bool = False
    conflict_details: Optional[str] = None
    created_at: str = Field(default_factory=current_iso_time)


class CaseEvaluationScore(BaseModel):
    """
    Comprehensive benchmark score for a single evaluation scenario.
    Captures all 12 operational evaluation dimensions.
    """

    case_id: str
    scenario_type: str = "recurrent_incident"
    memory_mode: Literal["MEMORY_ENABLED", "MEMORY_DISABLED"]
    
    # 1. Root Cause Identification
    top_1_root_cause_hit: bool = False
    top_3_root_cause_hit: bool = False
    
    # 2. Causal Reasoning Quality (0.0 to 1.0)
    causal_reasoning_score: float = 0.0

    # 3. Evidence Grounding
    evidence_grounding_score: float = 0.0
    recommendation_grounding: bool = True

    # 4. Memory Retrieval Quality
    retrieved_expected_historical: bool = False
    retrieval_precision: float = 0.0
    retrieval_recall: float = 0.0
    reciprocal_rank: float = 0.0

    # 5. Failed Mitigation Avoidance
    recalled_failed_mitigations: bool = False
    avoided_unsuccessful_mitigations: bool = True

    # 6. Recommended Action Quality (0.0 to 1.0)
    action_quality_score: float = 0.0

    # 7. Safety (Unsafe recommendations flagged/prevented)
    is_safe_recommendation: bool = True

    # 8. Calibration & Uncertainty
    appropriate_uncertainty: bool = True
    confidence_calibration_error: float = 0.0

    # 9. Novel Incident Handling
    novel_handling_score: float = 1.0

    # 10. False Memory Retrieval
    false_recall_flagged: bool = False

    # 11. Investigation Consistency
    consistency_score: float = 1.0

    # 12. Human Verification Compliance
    human_verification_compliant: bool = True

    # Composite Normalized Score (0.0 - 100.0)
    overall_score: float = Field(..., ge=0.0, le=100.0)
    explanation: str = ""
    detailed_rubric_breakdown: Dict[str, float] = Field(default_factory=dict)
