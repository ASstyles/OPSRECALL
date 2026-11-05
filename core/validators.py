"""
Data models and validation schemas for OPSRECALL.
Defines strongly-typed Pydantic schemas for incidents, investigations,
recalled memories, evaluations, and human resolution feedback.
"""

from __future__ import annotations

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
    suspected_cause: Optional[str] = Field(default=None, description="Initial triage suspicion")
    actual_verified_root_cause: Optional[str] = Field(default=None, description="Confirmed root cause")
    diagnostic_actions_attempted: List[str] = Field(default_factory=list)
    failed_mitigation_attempts: List[str] = Field(default_factory=list)
    successful_mitigation: Optional[str] = Field(default=None)
    resolution: Optional[str] = Field(default=None)
    resolution_outcome: Optional[str] = Field(default=None)
    verification_evidence: Optional[str] = Field(default=None)
    lessons_learned: Optional[str] = Field(default=None)
    data_type: str = Field(default="SIMULATED_INCIDENT", description="Explicit simulation label")


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
    is_distractor: bool = False
    requires_uncertainty: bool = False
    rubric_notes: str = ""


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


class Hypothesis(BaseModel):
    """A root-cause hypothesis with evidence grounding."""

    rank: int = Field(..., ge=1, le=3)
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


class FailedApproachWarning(BaseModel):
    """Historical failed fix to avoid repeating."""

    approach: str
    why_failed: str
    historical_source_incident: str


class InvestigationResult(BaseModel):
    """Complete structured investigation report."""

    investigation_id: str
    incident_id: str
    mode: Literal["MEMORY_ENABLED", "MEMORY_DISABLED"]
    executive_summary: str
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    evidence_summary: List[str] = Field(default_factory=list)
    recalled_memories: List[RecalledMemoryItem] = Field(default_factory=list)
    historical_incidents_referenced: List[str] = Field(default_factory=list)
    previous_failed_approaches: List[FailedApproachWarning] = Field(default_factory=list)
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
    retained_to_hindsight: bool = False
    hindsight_operation_id: Optional[str] = None
    created_at: str = Field(default_factory=current_iso_time)


class CaseEvaluationScore(BaseModel):
    """Benchmark evaluation score for a single case and memory mode."""

    case_id: str
    scenario_type: str = "recurrent_incident"
    memory_mode: Literal["MEMORY_ENABLED", "MEMORY_DISABLED"]
    top_3_root_cause_hit: bool
    retrieved_expected_historical: bool
    recalled_failed_mitigations: bool
    avoided_unsuccessful_mitigations: bool
    false_recall_flagged: bool
    appropriate_uncertainty: bool
    recommendation_grounding: bool = True
    overall_score: float = Field(..., ge=0.0, le=100.0)
    explanation: str

