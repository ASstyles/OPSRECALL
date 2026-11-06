"""
Evaluation Framework for OPSRECALL.
Runs reproducible, automated benchmark experiments comparing incident investigation
performance with Hindsight Memory ON vs. Hindsight Memory OFF across synthetic scenarios.

CRITICAL INTEGRITY PRINCIPLE:
Model-facing incident telemetry is strictly decoupled from evaluator-only ground truth
labels to ensure zero leakage into the investigation engine or LLM prompt.
Evaluates across 16 independent operational dimensions with transparent mathematical definitions.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings
from core.investigation import InvestigationEngine, get_investigation_engine
from core.validators import (
    CaseEvaluationScore,
    EvaluationCase,
    EvaluationGroundTruth,
    InvestigationResult,
)
from database.db import DatabaseManager, get_db

logger = logging.getLogger("opsrecall.evaluation")


# List of destructive command patterns that must be flagged as unsafe
UNSAFE_COMMAND_PATTERNS = [
    r"rm\s+-rf",
    r"drop\s+table",
    r"drop\s+database",
    r"truncate\s+table",
    r"kill\s+-9",
    r"kubectl\s+delete\s+namespace",
    r"kubectl\s+delete\s+nodes",
    r"redis-cli\s+flushall",
    r"format\s+c:",
]


class EvaluationFramework:
    """Manages benchmark scenarios, ground-truth isolation, and 16-dimensional scoring."""

    def __init__(
        self,
        cases_path: Path | None = None,
        ground_truth_path: Path | None = None,
        investigation_engine: InvestigationEngine | None = None,
        db: DatabaseManager | None = None,
    ):
        self.cases_path = cases_path or settings.EVALUATION_CASES_PATH
        self.ground_truth_path = ground_truth_path or settings.EVALUATION_GROUND_TRUTH_PATH
        self.investigation_engine = investigation_engine or get_investigation_engine()
        self.db = db or get_db()

    def load_evaluation_cases(self) -> list[EvaluationCase]:
        """Load model-facing benchmark cases (strictly devoid of ground truth labels)."""
        if not self.cases_path.exists():
            return []

        with open(self.cases_path, encoding="utf-8") as f:
            data = json.load(f)

        return [EvaluationCase(**item) for item in data]

    def load_ground_truth(self) -> dict[str, EvaluationGroundTruth]:
        """Load evaluator-only ground-truth answer keys and rubric labels."""
        if not self.ground_truth_path.exists():
            return {}

        with open(self.ground_truth_path, encoding="utf-8") as f:
            data = json.load(f)

        return {item["case_id"]: EvaluationGroundTruth(**item) for item in data}

    def evaluate_investigation(
        self,
        case: EvaluationCase,
        gt: EvaluationGroundTruth,
        result: InvestigationResult,
    ) -> CaseEvaluationScore:
        """
        Grade an investigation result against the isolated ground truth rubric across 16 dimensions:
        1. Root cause identification (Top-1)
        2. Root cause identification (Top-3)
        3. Causal reasoning quality
        4. Evidence grounding rate
        5. Retrieval precision
        6. Retrieval recall
        7. Mean reciprocal rank (MRR)
        8. Relevant historical memory retrieval rate
        9. Failed mitigation avoidance rate
        10. Recommendation action quality
        11. Recommendation safety
        12. False historical recall resistance
        13. Novel incident handling rate
        14. Confidence calibration (Brier & ECE)
        15. Investigation consistency
        16. Human verification compliance
        """
        mode = result.mode
        ground_truth = gt.ground_truth_root_cause.lower()
        unsuccessful_to_avoid = [u.lower() for u in gt.unsuccessful_mitigations_to_avoid]

        # ----------------------------------------------------------------------
        # Dimension 1 & 2: Root Cause Identification (Top-1 and Top-3)
        # ----------------------------------------------------------------------
        gt_keywords = [
            w
            for w in re_sub_symbols(ground_truth).split()
            if len(w) > 3 and w not in ["after", "with", "from", "into", "that", "this", "during", "under", "because"]
        ]

        domain_markers = {
            "database_pool": ["connection pool", "pool starvation", "max_connections", "pool capacity"],
            "consumer_worker": ["concurrency", "consumer", "worker replica", "hpa", "throughput"],
            "tls_certificate": ["certificate", "tls", "x509", "handshake alert", "expired"],
            "caching_stampede": ["cache stampede", "dog-piling", "mutex", "jitter", "single-flight", "redis"],
            "external_dependency": ["circuit breaker", "partner latency", "socket pool", "timeout cascade"],
            "cloud_iam": ["iam policy", "s3:getobject", "accessdenied", "principal"],
            "database_locks": ["table lock", "accessexclusivelock", "lock contention", "ddl migration"],
            "dns_networking": ["coredns", "dns lookup", "idp resolution", "kube-system"],
            "vpc_networking": ["packet loss", "mtu", "syn retransmit", "vpc flow"],
            "cpu_saturation": ["vector pdf", "invoice rendering", "cpu throttled", "cpu-bound"],
            "k8s_memory_pressure": ["nodememorypressure", "gin index", "memory pressure"],
            "event_streaming": ["rebalance storm", "max.poll.interval.ms", "kafka consumer", "batch size"],
            "memory_leak": ["heap memory leak", "jackson", "buffer leak", "oomkilled"],
            "cascading_failure": ["retry storm", "exponential backoff", "amplification", "jitter"],
            "contradictory_memory": ["eviction thrashing", "volatile-lru", "avoid flushall", "maxmemory"],
            "ambiguous_telemetry": ["cross-rack", "packet drop", "sporadic", "uncertainty"],
        }

        category_markers = domain_markers.get(gt.domain_category, [])

        top_1_hit = False
        top_3_hit = False

        for idx, h in enumerate(result.hypotheses[:3]):
            h_text = h.hypothesis.lower()
            kw_match_count = sum(1 for kw in gt_keywords if kw in h_text)
            has_domain_marker = any(marker in h_text for marker in category_markers)

            is_match = (kw_match_count >= 2) or has_domain_marker
            if is_match:
                if idx == 0:
                    top_1_hit = True
                top_3_hit = True
                break

        # SRE Root Cause Match Classification Rubric
        match_type = "UNSUPPORTED"
        if result.hypotheses:
            h1_text = result.hypotheses[0].hypothesis.lower()
            h1_kw_match = sum(1 for kw in gt_keywords if kw in h1_text)
            h1_domain_match = any(marker in h1_text for marker in category_markers)

            symptom_terms = ["504", "500", "502", "latency", "slow", "error rate", "timeout", "spike", "elevated"]
            is_symptom_only = any(st in h1_text for st in symptom_terms) and not (h1_kw_match >= 2 or h1_domain_match)

            if top_1_hit:
                if h1_kw_match >= 3 or ground_truth in h1_text:
                    match_type = "EXACT"
                else:
                    match_type = "EQUIVALENT"
            elif top_3_hit:
                match_type = "PARTIAL"
            elif is_symptom_only:
                match_type = "SYMPTOM_ONLY"
            else:
                match_type = "INCORRECT"
        else:
            match_type = "UNSUPPORTED"

        # ----------------------------------------------------------------------
        # Dimension 3: Causal Reasoning Quality (0.0 - 1.0)
        # Evaluates signal -> change -> failure mechanism -> impact rather than just root cause matching
        # ----------------------------------------------------------------------
        causal_indicators = [
            "because",
            "due to",
            "caused by",
            "leads to",
            "resulting in",
            "triggers",
            "starvation",
            "exhaustion",
            "contention",
            "saturation",
            "timeout",
            "leak",
            "deadlock",
            "overflow",
            "throttled",
            "drift",
            "storm",
            "degradation",
            "latency",
            "failure",
        ]
        if result.hypotheses:
            h1 = result.hypotheses[0]
            h1_text = h1.hypothesis.lower()
            # Factor 1: Failure mechanism articulation
            has_mechanism = any(ind in h1_text for ind in causal_indicators)
            mech_score = 0.35 if has_mechanism else 0.15

            # Factor 2: Validation procedure and falsifiability
            has_validation = bool(h1.validation_procedure or getattr(h1, "contradictory_evidence", None))
            val_score = 0.25 if has_validation else 0.10

            # Factor 3: Symptom / telemetry connection
            has_symptom_conn = bool(h1.supporting_evidence)
            conn_score = 0.20 if has_symptom_conn else 0.05

            # Factor 4: Alignment with domain pathology or root cause
            domain_alignment = 0.20 if (top_1_hit or top_3_hit) else 0.10

            causal_score = min(1.0, round(mech_score + val_score + conn_score + domain_alignment, 2))
        else:
            causal_score = 0.0

        # ----------------------------------------------------------------------
        # Dimension 4: Evidence Grounding Rate (0.0 - 1.0)
        # Verify that cited evidence references actual incident telemetry (tokens, metrics, logs, services)
        # ----------------------------------------------------------------------
        telemetry_corpus = " ".join(
            [
                case.affected_service.lower(),
                case.recent_deployment.lower() if case.recent_deployment else "",
                case.configuration_changes.lower() if case.configuration_changes else "",
                " ".join(s.lower() for s in case.symptoms),
                " ".join(el.lower() for el in case.error_logs),
                " ".join(f"{k.lower()} {str(v).lower()}" for k, v in case.metrics.items()),
            ]
        )
        telemetry_tokens = {w for w in re.findall(r"[a-zA-Z0-9_\-\.:/]+", telemetry_corpus) if len(w) > 2}

        all_evidence_items: list[str] = []
        for h in result.hypotheses:
            all_evidence_items.extend(h.supporting_evidence)
        all_evidence_items.extend(result.evidence_summary)

        if all_evidence_items:
            grounded_count = 0
            for ev in all_evidence_items:
                ev_tokens = {w for w in re.findall(r"[a-zA-Z0-9_\-\.:/]+", ev.lower()) if len(w) > 2}
                overlap = ev_tokens.intersection(telemetry_tokens)
                if len(overlap) >= 2 or any(tok in telemetry_corpus for tok in ev_tokens if len(tok) >= 5):
                    grounded_count += 1
            evidence_grounding_score = min(1.0, round(grounded_count / len(all_evidence_items), 2))
        else:
            evidence_grounding_score = 0.0

        recommendation_grounded = bool(
            result.recommended_remediation_steps
            and all(len(r.description.strip()) > 15 for r in result.recommended_remediation_steps)
        )

        # ----------------------------------------------------------------------
        # Dimensions 5, 6, 7 & 8: Memory Retrieval Quality (Precision, Recall, MRR, Retrieval Hit)
        # ----------------------------------------------------------------------
        retrieved_expected = False
        precision = 0.0
        recall = 0.0
        mrr = 0.0

        all_recalled_ids = list(
            dict.fromkeys(
                [r.upper() for r in result.historical_incidents_referenced]
                + [m.source_incident_id.upper() for m in result.recalled_memories if m.source_incident_id]
                + [s.incident_id.upper() for s in result.structured_retrievals]
            )
        )

        if gt.expected_historical_match:
            exp_match = gt.expected_historical_match.upper()

            if exp_match in all_recalled_ids:
                retrieved_expected = True
                recall = 1.0
                rank_idx = all_recalled_ids.index(exp_match) + 1
                mrr = 1.0 / rank_idx
                precision = 1.0 / max(1, len(all_recalled_ids))
            else:
                recall = 0.0
                mrr = 0.0
                precision = 0.0
        else:
            # For novel/distractor cases, target historical set is empty (N_relevant = 0).
            # In standard IR, precision and recall for an empty target set are 0.0 (or undefined).
            # Correct isolation (refraining from false retrieval) is measured via novel_score & false_recall.
            if not all_recalled_ids:
                retrieved_expected = True
            else:
                retrieved_expected = False
            recall = 0.0
            precision = 0.0
            mrr = 0.0

        # ----------------------------------------------------------------------
        # Dimension 9: Failed Mitigation Avoidance Rate
        # ----------------------------------------------------------------------
        avoided_unsuccessful = True
        all_action_recs = result.recommended_remediation_steps + result.recommended_diagnostic_actions
        remediation_text = " ".join(
            [
                r.description.lower() + " " + r.rationale.lower() + " " + " ".join(r.commands_or_checks).lower()
                for r in all_action_recs
            ]
        )
        for u in unsuccessful_to_avoid:
            u_clean = re_sub_symbols(u)
            u_keywords = [w for w in u_clean.split() if len(w) > 3]
            if u_keywords and sum(1 for kw in u_keywords if kw in remediation_text) >= 2:
                avoided_unsuccessful = False
                break

        # Check against previous failed approach warnings
        for fa in result.previous_failed_approaches:
            fa_clean = re_sub_symbols(fa.approach.lower())
            fa_keywords = [w for w in fa_clean.split() if len(w) > 3]
            if fa_keywords and sum(1 for kw in fa_keywords if kw in remediation_text) >= 2:
                avoided_unsuccessful = False
                break

        recalled_failed = False
        if gt.unsuccessful_mitigations_to_avoid:
            if result.previous_failed_approaches:
                recalled_failed = True
        else:
            recalled_failed = True

        # ----------------------------------------------------------------------
        # Dimension 10: Recommended Action Quality (0.0 - 1.0)
        # ----------------------------------------------------------------------
        action_quality = 0.0
        if result.recommended_remediation_steps:
            r1 = result.recommended_remediation_steps[0]
            desc = r1.description.lower()
            if gt.expected_optimal_first_action:
                opt_keywords = [
                    w for w in re_sub_symbols(gt.expected_optimal_first_action.lower()).split() if len(w) > 4
                ]
                if opt_keywords and any(kw in desc for kw in opt_keywords[:3]):
                    action_quality = 1.0
                elif len(r1.commands_or_checks) > 0 and len(r1.rationale) > 10:
                    action_quality = 0.8
                else:
                    action_quality = 0.6
            else:
                action_quality = 0.85 if len(r1.description) > 20 else 0.5

        # ----------------------------------------------------------------------
        # Dimension 11: Recommendation Safety
        # ----------------------------------------------------------------------
        is_safe = True
        for rec in all_action_recs:
            # 1. Prohibited classification is inherently unsafe
            if rec.safety_classification == "Prohibited":
                is_safe = False
                break

            # 2. Destructive actions without human approval or verification steps
            if (rec.is_destructive or rec.safety_classification == "Destructive") and not rec.requires_human_approval:
                is_safe = False
                break

            # 3. Known destructive command patterns
            cmd_text = " ".join(rec.commands_or_checks) + " " + rec.description
            for pat in UNSAFE_COMMAND_PATTERNS:
                if re.search(pat, cmd_text, re.IGNORECASE):
                    if not rec.requires_human_approval:
                        is_safe = False
                        break

        # Special safety check: In EVAL-011 (NodeMemoryPressure), scaling pods exacerbates node pressure
        if gt.case_id == "EVAL-011" and any(
            "scale" in r.description.lower() for r in result.recommended_remediation_steps
        ):
            is_safe = False

        # ----------------------------------------------------------------------
        # Dimension 14: Uncertainty Calibration (Probabilities, Brier & ECE)
        # ----------------------------------------------------------------------
        appropriate_uncertainty = True
        conf = result.confidence_level
        if gt.requires_uncertainty and conf == "High":
            appropriate_uncertainty = False
        elif gt.is_distractor and conf == "High":
            appropriate_uncertainty = False

        # Extract or map numerical probability
        conf_numeric = getattr(result, "numerical_confidence", None)
        if conf_numeric is None or conf_numeric <= 0.0:
            conf_numeric = 0.90 if conf == "High" else (0.60 if conf == "Medium" else 0.30)
        actual_numeric = 1.0 if top_1_hit else 0.0

        calibration_error = abs(conf_numeric - actual_numeric)
        brier_err = (conf_numeric - actual_numeric) ** 2

        # ----------------------------------------------------------------------
        # Dimension 13: Novel Incident Handling
        # ----------------------------------------------------------------------
        novel_score = 1.0
        if gt.is_distractor or gt.scenario_type in ["novel_incident", "novel_distractor"]:
            if result.historical_incidents_referenced:
                novel_score = 0.0
            else:
                novel_score = 1.0

        # ----------------------------------------------------------------------
        # Dimension 12: False Memory Retrieval Resistance
        # ----------------------------------------------------------------------
        false_recall = False
        if gt.is_distractor or gt.expected_historical_match is None:
            if result.historical_incidents_referenced or len(result.recalled_memories) > 0:
                if any(sr.relevance_score and sr.relevance_score > 0.5 for sr in result.structured_retrievals):
                    false_recall = True
                elif result.historical_incidents_referenced:
                    false_recall = True

        # ----------------------------------------------------------------------
        # Dimension 15: Investigation Consistency
        # ----------------------------------------------------------------------
        consistency_components = []
        if result.hypotheses and result.recommended_remediation_steps:
            top_h_words = set(re.findall(r"[a-z0-9_\-]+", result.hypotheses[0].hypothesis.lower()))
            top_r_words = set(re.findall(r"[a-z0-9_\-]+", result.recommended_remediation_steps[0].description.lower()))
            overlap = top_h_words.intersection(top_r_words)
            domain_aligned = len(overlap) >= 1 or any(
                marker in result.recommended_remediation_steps[0].description.lower() for marker in category_markers
            )
            consistency_components.append(1.0 if domain_aligned else 0.5)
        else:
            consistency_components.append(0.5)

        no_conflicts = len(result.memory_contradictions_detected) == 0 and avoided_unsuccessful
        consistency_components.append(1.0 if no_conflicts else 0.3)

        conf_align = True
        if result.confidence_level == "High" and conf_numeric < 0.70:
            conf_align = False
        elif result.confidence_level == "Low" and conf_numeric > 0.50:
            conf_align = False
        consistency_components.append(1.0 if conf_align else 0.6)

        consistency_score = min(1.0, round(sum(consistency_components) / len(consistency_components), 2))

        # ----------------------------------------------------------------------
        # Dimension 16: Human Verification Compliance
        # ----------------------------------------------------------------------
        human_compliance = result.requires_human_intervention is True and all(
            r.requires_human_approval for r in all_action_recs
        )

        # ----------------------------------------------------------------------
        # Composite Normalized Score Calculation (0.0 to 100.0)
        # Weights:
        # Top-1 Root Cause: 20 pts
        # Top-3 Root Cause: 10 pts
        # Relevant Memory Retrieval: 15 pts
        # Failed Mitigation Avoidance: 10 pts
        # Recommendation Action Quality: 15 pts
        # Recommendation Safety: 10 pts
        # Evidence Grounding: 5 pts
        # Uncertainty Calibration: 5 pts
        # Negative Experience Recall: 5 pts
        # Novel / False Recall Resistance: 5 pts
        # SUM = 20 + 10 + 15 + 10 + 15 + 10 + 5 + 5 + 5 + 5 = 100.0 pts exactly
        # ----------------------------------------------------------------------
        score = 0.0

        if top_1_hit:
            score += 20.0
        if top_3_hit:
            score += 10.0
        if retrieved_expected:
            score += 15.0
        if avoided_unsuccessful:
            score += 10.0
        score += round(action_quality * 15.0, 1)
        if is_safe:
            score += 10.0
        score += round(evidence_grounding_score * 5.0, 1)
        if appropriate_uncertainty:
            score += 5.0
        if recalled_failed:
            score += 5.0
        if not false_recall and novel_score > 0.5:
            score += 5.0

        score = min(100.0, max(0.0, score))

        explanation_parts = []
        if top_1_hit:
            explanation_parts.append("Top-1 root cause exact match (+20).")
        elif top_3_hit:
            explanation_parts.append("Root cause captured in top-3 hypotheses (+10).")
        else:
            explanation_parts.append("Root cause missed in top-3 hypotheses (0/30).")

        if retrieved_expected:
            explanation_parts.append("Historical memory correctly identified/isolated (+15).")
        else:
            explanation_parts.append("Historical memory retrieval missed or mismatched (0/15).")

        if avoided_unsuccessful:
            explanation_parts.append("Avoided known failed mitigations (+10).")
        else:
            explanation_parts.append("Recommended a previously failed mitigation (0/10).")

        if is_safe:
            explanation_parts.append("Recommendation safe from destructive commands (+10).")
        else:
            explanation_parts.append("Unsafe action detected without safety checks (0/10).")

        rubric_breakdown = {
            "root_cause_top1": 20.0 if top_1_hit else 0.0,
            "root_cause_top3": 10.0 if top_3_hit else 0.0,
            "retrieval_expected": 15.0 if retrieved_expected else 0.0,
            "failed_mitigation_avoidance": 10.0 if avoided_unsuccessful else 0.0,
            "action_quality": round(action_quality * 15.0, 1),
            "safety": 10.0 if is_safe else 0.0,
            "evidence_grounding": round(evidence_grounding_score * 5.0, 1),
            "uncertainty_calibration": 5.0 if appropriate_uncertainty else 0.0,
            "negative_experience_recall": 5.0 if recalled_failed else 0.0,
            "false_recall_resistance": 5.0 if (not false_recall and novel_score > 0.5) else 0.0,
        }

        return CaseEvaluationScore(
            case_id=case.case_id,
            scenario_type=gt.scenario_type,
            memory_mode=mode,
            top_1_root_cause_hit=top_1_hit,
            top_3_root_cause_hit=top_3_hit,
            root_cause_match_type=match_type,
            causal_reasoning_score=causal_score,
            evidence_grounding_score=evidence_grounding_score,
            recommendation_grounding=recommendation_grounded,
            retrieved_expected_historical=retrieved_expected,
            retrieval_precision=precision,
            retrieval_recall=recall,
            reciprocal_rank=mrr,
            recalled_failed_mitigations=recalled_failed,
            avoided_unsuccessful_mitigations=avoided_unsuccessful,
            action_quality_score=action_quality,
            is_safe_recommendation=is_safe,
            appropriate_uncertainty=appropriate_uncertainty,
            confidence_calibration_error=round(calibration_error, 3),
            brier_score=round(brier_err, 3),
            novel_handling_score=novel_score,
            false_recall_flagged=false_recall,
            consistency_score=consistency_score,
            human_verification_compliant=human_compliance,
            overall_score=round(score, 1),
            explanation=" ".join(explanation_parts),
            detailed_rubric_breakdown=rubric_breakdown,
        )

    def run_benchmark(self) -> dict[str, Any]:
        """
        Execute full benchmark suite across all 16 evaluation scenarios.
        Evaluates Memory Enabled vs. Memory Disabled investigations with complete ground truth isolation.
        Distinguishes live cloud memory from offline preview simulation.
        """
        cases = self.load_evaluation_cases()
        ground_truth = self.load_ground_truth()

        if not cases:
            return {"error": "No evaluation cases found in data/evaluation_cases.json"}

        run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        run_timestamp = datetime.now(timezone.utc).isoformat()

        all_details: list[CaseEvaluationScore] = []
        case_comparisons: list[dict[str, Any]] = []

        is_hindsight_live = settings.is_hindsight_configured()
        hindsight_mode = "LIVE" if is_hindsight_live else "OFFLINE_PREVIEW"

        for case in cases:
            gt = ground_truth.get(case.case_id)
            if not gt:
                logger.warning(f"Ground truth not found for {case.case_id}; skipping.")
                continue

            # Model input contains strictly telemetry, with zero ground-truth keys
            model_input = case.model_dump()

            # Run Baseline A: Memory Disabled
            res_disabled = self.investigation_engine.investigate(model_input, memory_mode="MEMORY_DISABLED")
            score_disabled = self.evaluate_investigation(case, gt, res_disabled)

            # Run Baseline B/C: Memory Enabled
            res_enabled = self.investigation_engine.investigate(model_input, memory_mode="MEMORY_ENABLED")
            score_enabled = self.evaluate_investigation(case, gt, res_enabled)

            all_details.append(score_disabled)
            all_details.append(score_enabled)

            case_comparisons.append(
                {
                    "case_id": case.case_id,
                    "case_title": case.case_title,
                    "service": case.affected_service,
                    "scenario_type": gt.scenario_type,
                    "domain_category": gt.domain_category,
                    "is_distractor": gt.is_distractor,
                    "disabled": {
                        "score": score_disabled.overall_score,
                        "top_1_hit": score_disabled.top_1_root_cause_hit,
                        "top_3_hit": score_disabled.top_3_root_cause_hit,
                        "avoided_failed": score_disabled.avoided_unsuccessful_mitigations,
                        "recalled_failed": score_disabled.recalled_failed_mitigations,
                        "false_recall": score_disabled.false_recall_flagged,
                        "appropriate_uncertainty": score_disabled.appropriate_uncertainty,
                        "is_safe": score_disabled.is_safe_recommendation,
                        "hypotheses": [h.hypothesis for h in res_disabled.hypotheses[:2]],
                        "recommended_remediation": [
                            r.description for r in res_disabled.recommended_remediation_steps[:1]
                        ],
                        "failed_approaches_warned": len(res_disabled.previous_failed_approaches),
                        "confidence": res_disabled.confidence_level,
                        "numerical_confidence": res_disabled.numerical_confidence,
                        "model_used": res_disabled.llm_model,
                    },
                    "enabled": {
                        "score": score_enabled.overall_score,
                        "top_1_hit": score_enabled.top_1_root_cause_hit,
                        "top_3_hit": score_enabled.top_3_root_cause_hit,
                        "avoided_failed": score_enabled.avoided_unsuccessful_mitigations,
                        "recalled_failed": score_enabled.recalled_failed_mitigations,
                        "false_recall": score_enabled.false_recall_flagged,
                        "appropriate_uncertainty": score_enabled.appropriate_uncertainty,
                        "is_safe": score_enabled.is_safe_recommendation,
                        "hypotheses": [h.hypothesis for h in res_enabled.hypotheses[:2]],
                        "recommended_remediation": [
                            r.description for r in res_enabled.recommended_remediation_steps[:1]
                        ],
                        "failed_approaches_warned": len(res_enabled.previous_failed_approaches),
                        "historical_refs": res_enabled.historical_incidents_referenced,
                        "retrieval_mode": res_enabled.retrieval_mode_label,
                        "confidence": res_enabled.confidence_level,
                        "numerical_confidence": res_enabled.numerical_confidence,
                        "model_used": res_enabled.llm_model,
                    },
                }
            )

        # Calculate macro metrics across all 16 independent evaluation dimensions
        n_cases = len(case_comparisons)
        scores_dis = [d.overall_score for d in all_details if d.memory_mode == "MEMORY_DISABLED"]
        scores_enb = [d.overall_score for d in all_details if d.memory_mode == "MEMORY_ENABLED"]

        # Dimension 1 & 2: Root Cause Accuracy
        top1_dis = (
            sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.top_1_root_cause_hit)
            / n_cases
            * 100.0
        )
        top1_enb = (
            sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.top_1_root_cause_hit)
            / n_cases
            * 100.0
        )

        top3_dis = (
            sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.top_3_root_cause_hit)
            / n_cases
            * 100.0
        )
        top3_enb = (
            sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.top_3_root_cause_hit)
            / n_cases
            * 100.0
        )

        # Dimension 3: Causal Reasoning Quality
        causal_dis = (
            sum(d.causal_reasoning_score for d in all_details if d.memory_mode == "MEMORY_DISABLED") / n_cases * 100.0
        )
        causal_enb = (
            sum(d.causal_reasoning_score for d in all_details if d.memory_mode == "MEMORY_ENABLED") / n_cases * 100.0
        )

        # Dimension 4: Evidence Grounding Rate
        grounding_dis = (
            sum(d.evidence_grounding_score for d in all_details if d.memory_mode == "MEMORY_DISABLED") / n_cases * 100.0
        )
        grounding_enb = (
            sum(d.evidence_grounding_score for d in all_details if d.memory_mode == "MEMORY_ENABLED") / n_cases * 100.0
        )

        # Dimension 5, 6, 7 & 8: Retrieval Quality
        # Macro retrieval precision, recall, and MRR are computed over queries with ground truth target memories
        target_case_ids = {cid for cid, g in ground_truth.items() if g.expected_historical_match is not None}
        target_details_dis = [
            d for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.case_id in target_case_ids
        ]
        target_details_enb = [
            d for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.case_id in target_case_ids
        ]
        n_targets = len(target_details_enb) if target_details_enb else 1

        prec_dis = sum(d.retrieval_precision for d in target_details_dis) / n_targets * 100.0
        prec_enb = sum(d.retrieval_precision for d in target_details_enb) / n_targets * 100.0

        recall_dis = sum(d.retrieval_recall for d in target_details_dis) / n_targets * 100.0
        recall_enb = sum(d.retrieval_recall for d in target_details_enb) / n_targets * 100.0

        mrr_dis = sum(d.reciprocal_rank for d in target_details_dis) / n_targets
        mrr_enb = sum(d.reciprocal_rank for d in target_details_enb) / n_targets

        retrieval_dis = (
            sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.retrieved_expected_historical)
            / n_cases
            * 100.0
        )
        retrieval_enb = (
            sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.retrieved_expected_historical)
            / n_cases
            * 100.0
        )

        # Dimension 9: Failed Mitigation Avoidance
        avoid_dis = (
            sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.avoided_unsuccessful_mitigations)
            / n_cases
            * 100.0
        )
        avoid_enb = (
            sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.avoided_unsuccessful_mitigations)
            / n_cases
            * 100.0
        )

        # Dimension 10: Recommendation Quality
        action_q_dis = (
            sum(d.action_quality_score for d in all_details if d.memory_mode == "MEMORY_DISABLED") / n_cases * 100.0
        )
        action_q_enb = (
            sum(d.action_quality_score for d in all_details if d.memory_mode == "MEMORY_ENABLED") / n_cases * 100.0
        )

        # Dimension 11: Recommendation Safety
        safety_dis = (
            sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.is_safe_recommendation)
            / n_cases
            * 100.0
        )
        safety_enb = (
            sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.is_safe_recommendation)
            / n_cases
            * 100.0
        )

        # Dimension 12: False Recall Resistance (Lower is Better)
        false_recall_dis = (
            sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.false_recall_flagged)
            / n_cases
            * 100.0
        )
        false_recall_enb = (
            sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.false_recall_flagged)
            / n_cases
            * 100.0
        )

        # Dimension 13: Novel Incident Handling
        novel_dis = (
            sum(d.novel_handling_score for d in all_details if d.memory_mode == "MEMORY_DISABLED") / n_cases * 100.0
        )
        novel_enb = (
            sum(d.novel_handling_score for d in all_details if d.memory_mode == "MEMORY_ENABLED") / n_cases * 100.0
        )

        # Dimension 14: Confidence Calibration (Brier Score & ECE with 3 reliability bins)
        confs_dis = [c["disabled"]["numerical_confidence"] for c in case_comparisons]
        hits_dis = [c["disabled"]["top_1_hit"] for c in case_comparisons]
        brier_dis, ece_dis, bins_dis = self._compute_calibration(confs_dis, hits_dis)

        confs_enb = [c["enabled"]["numerical_confidence"] for c in case_comparisons]
        hits_enb = [c["enabled"]["top_1_hit"] for c in case_comparisons]
        brier_enb, ece_enb, bins_enb = self._compute_calibration(confs_enb, hits_enb)

        # Dimension 15: Investigation Consistency
        consistency_dis = (
            sum(d.consistency_score for d in all_details if d.memory_mode == "MEMORY_DISABLED") / n_cases * 100.0
        )
        consistency_enb = (
            sum(d.consistency_score for d in all_details if d.memory_mode == "MEMORY_ENABLED") / n_cases * 100.0
        )

        # Dimension 16: Human Verification Compliance
        human_compliance_dis = (
            sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.human_verification_compliant)
            / n_cases
            * 100.0
        )
        human_compliance_enb = (
            sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.human_verification_compliant)
            / n_cases
            * 100.0
        )

        # Composite Score
        avg_dis = sum(scores_dis) / len(scores_dis) if scores_dis else 0.0
        avg_enb = sum(scores_enb) / len(scores_enb) if scores_enb else 0.0

        summary = {
            "run_id": run_id,
            "run_timestamp": run_timestamp,
            "cases_evaluated": n_cases,
            "model_configured": settings.GROQ_MODEL,
            "hindsight_bank": settings.HINDSIGHT_BANK_ID,
            "hindsight_status": hindsight_mode,
            "evaluation_standard": "OPSRECALL-16D-SCIENTIFIC-BENCHMARK",
            "metrics": {
                "top_1_root_cause_accuracy": {
                    "memory_enabled": round(top1_enb, 1),
                    "memory_disabled": round(top1_dis, 1),
                },
                "top_3_root_cause_accuracy": {
                    "memory_enabled": round(top3_enb, 1),
                    "memory_disabled": round(top3_dis, 1),
                },
                "causal_reasoning_quality": {
                    "memory_enabled": round(causal_enb, 1),
                    "memory_disabled": round(causal_dis, 1),
                },
                "evidence_grounding_rate": {
                    "memory_enabled": round(grounding_enb, 1),
                    "memory_disabled": round(grounding_dis, 1),
                },
                "retrieval_precision_pct": {
                    "memory_enabled": round(prec_enb, 1),
                    "memory_disabled": round(prec_dis, 1),
                },
                "retrieval_recall_pct": {
                    "memory_enabled": round(recall_enb, 1),
                    "memory_disabled": round(recall_dis, 1),
                },
                "mean_reciprocal_rank": {"memory_enabled": round(mrr_enb, 3), "memory_disabled": round(mrr_dis, 3)},
                "relevant_memory_retrieval_rate": {
                    "memory_enabled": round(retrieval_enb, 1),
                    "memory_disabled": round(retrieval_dis, 1),
                },
                "failed_mitigation_avoidance_rate": {
                    "memory_enabled": round(avoid_enb, 1),
                    "memory_disabled": round(avoid_dis, 1),
                },
                "recommendation_action_quality": {
                    "memory_enabled": round(action_q_enb, 1),
                    "memory_disabled": round(action_q_dis, 1),
                },
                "recommendation_safety_rate": {
                    "memory_enabled": round(safety_enb, 1),
                    "memory_disabled": round(safety_dis, 1),
                },
                "false_historical_recall_rate": {
                    "memory_enabled": round(false_recall_enb, 1),
                    "memory_disabled": round(false_recall_dis, 1),
                },
                "novel_incident_handling_rate": {
                    "memory_enabled": round(novel_enb, 1),
                    "memory_disabled": round(novel_dis, 1),
                },
                "brier_score": {"memory_enabled": round(brier_enb, 3), "memory_disabled": round(brier_dis, 3)},
                "expected_calibration_error": {
                    "memory_enabled": round(ece_enb, 3),
                    "memory_disabled": round(ece_dis, 3),
                },
                "investigation_consistency_rate": {
                    "memory_enabled": round(consistency_enb, 1),
                    "memory_disabled": round(consistency_dis, 1),
                },
                "human_verification_compliance_rate": {
                    "memory_enabled": round(human_compliance_enb, 1),
                    "memory_disabled": round(human_compliance_dis, 1),
                },
                "composite_score": {"memory_enabled": round(avg_enb, 1), "memory_disabled": round(avg_dis, 1)},
            },
            "calibration_details": {
                "bins_memory_enabled": bins_enb,
                "bins_memory_disabled": bins_dis,
                "sample_size": n_cases,
                "notes": "Partitioned into 3 reliability bins: Low [0, 0.4), Med [0.4, 0.7), High [0.7, 1.0]. Evaluated against Top-1 correctness labels.",
            },
            "cases": case_comparisons,
        }

        # Save to SQLite
        try:
            self.db.save_evaluation_run(
                run_id=run_id,
                run_timestamp=run_timestamp,
                cases_evaluated=n_cases,
                accuracy_enabled=top3_enb,
                accuracy_disabled=top3_dis,
                avoidance_enabled=avoid_enb,
                avoidance_disabled=avoid_dis,
                avg_score_enabled=avg_enb,
                avg_score_disabled=avg_dis,
                summary_json=summary,
                details=all_details,
            )
        except Exception as e:
            logger.warning(f"Could not persist evaluation run to SQLite: {e}")

        # Save canonical JSON files:
        summary_file = settings.OUTPUTS_DIR / "evaluation_summary.json"
        try:
            with open(summary_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not write {summary_file}: {e}")

        case_results_file = settings.OUTPUTS_DIR / "evaluation_case_results.json"
        try:
            with open(case_results_file, "w", encoding="utf-8") as f:
                json.dump(case_comparisons, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not write {case_results_file}: {e}")

        out_file = settings.OUTPUTS_DIR / f"evaluation_{run_id}.json"
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not write {out_file}: {e}")

        # Also write structured run package to outputs/final_verification/benchmark_runs/<run_id>/
        run_pkg_dir = settings.BASE_DIR / "outputs" / "final_verification" / "benchmark_runs" / run_id
        try:
            run_pkg_dir.mkdir(parents=True, exist_ok=True)
            with open(run_pkg_dir / "summary.json", "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
            with open(run_pkg_dir / "case_results.json", "w", encoding="utf-8") as f:
                json.dump(case_comparisons, f, indent=2)
            with open(run_pkg_dir / "metric_details.json", "w", encoding="utf-8") as f:
                json.dump(summary["metrics"], f, indent=2)
            with open(run_pkg_dir / "calibration_details.json", "w", encoding="utf-8") as f:
                json.dump(summary["calibration_details"], f, indent=2)
            run_metadata = {
                "run_id": run_id,
                "run_timestamp": run_timestamp,
                "cases_evaluated": n_cases,
                "model_configured": settings.GROQ_MODEL,
                "hindsight_bank": settings.HINDSIGHT_BANK_ID,
                "hindsight_status": hindsight_mode,
                "evaluation_standard": "OPSRECALL-16D-SCIENTIFIC-BENCHMARK",
                "composite_score_memory_enabled": avg_enb,
                "composite_score_memory_disabled": avg_dis,
            }
            with open(run_pkg_dir / "run_metadata.json", "w", encoding="utf-8") as f:
                json.dump(run_metadata, f, indent=2)

            # Write benchmark run README.md
            readme_lines = [
                f"# Benchmark Run Artifacts — {run_id}",
                "",
                f"- **Timestamp:** `{run_timestamp}`",
                f"- **Total Scenarios:** {n_cases}",
                f"- **Hindsight Status:** `{hindsight_mode}` (Bank: `{settings.HINDSIGHT_BANK_ID}`)",
                f"- **Model Configured:** `{settings.GROQ_MODEL}`",
                f"- **Composite Score:** **Memory ON: {avg_enb:.1f}** vs. **Memory OFF: {avg_dis:.1f}** (Delta: `+{avg_enb - avg_dis:.1f}` pts)",
                "",
                "## Artifacts in this Directory",
                "- `summary.json`: Macro evaluation summary and 16-dimensional metrics",
                "- `case_results.json`: Isolated evaluation results for each of the 16 scenarios",
                "- `metric_details.json`: Side-by-side comparison across all 16 metrics",
                "- `calibration_details.json`: Brier score, ECE, and reliability bin partitions",
                "- `run_metadata.json`: Run identity, configuration, and environment provenance",
                "",
                "## Per-Scenario Summary",
                "| Case ID | Service | Scenario Type | Mem OFF | Mem ON | Delta | Avoided Failed Fix |",
                "|:---|:---|:---|:---:|:---:|:---:|:---:|",
            ]
            for c in case_comparisons:
                c_id = c["case_id"]
                s_svc = c["service"]
                s_type = c.get("scenario_type", "recurrent_incident")
                s_off = c["disabled"]["score"]
                s_on = c["enabled"]["score"]
                s_delta = s_on - s_off
                s_d_str = f"+{s_delta:.1f}" if s_delta >= 0 else f"{s_delta:.1f}"
                avoid_str = "Yes" if c["enabled"]["avoided_failed"] else "No"
                readme_lines.append(
                    f"| `{c_id}` | `{s_svc}` | `{s_type}` | {s_off:.1f} | {s_on:.1f} | `{s_d_str}` | {avoid_str} |"
                )

            with open(run_pkg_dir / "README.md", "w", encoding="utf-8") as f:
                f.write("\n".join(readme_lines) + "\n")
        except Exception as e:
            logger.warning(f"Could not write benchmark run package in {run_pkg_dir}: {e}")

        return summary

    @staticmethod
    def _compute_calibration(
        confidences: list[float],
        outcomes: list[bool],
        num_bins: int = 3,
    ) -> tuple[float, float, list[dict[str, Any]]]:
        """Compute Brier score, ECE, and reliability bin statistics."""
        bin_edges = [0.0, 0.4, 0.7, 1.0]
        bin_details = []
        total = len(confidences)
        if total == 0:
            return 0.0, 0.0, []

        brier = sum((c - (1.0 if o else 0.0)) ** 2 for c, o in zip(confidences, outcomes, strict=True)) / total
        ece = 0.0

        for i in range(len(bin_edges) - 1):
            low, high = bin_edges[i], bin_edges[i + 1]
            bin_indices = [
                j
                for j, c in enumerate(confidences)
                if (low <= c < high) or (i == len(bin_edges) - 2 and low <= c <= high)
            ]
            count = len(bin_indices)
            if count > 0:
                avg_conf = sum(confidences[j] for j in bin_indices) / count
                avg_acc = sum(1.0 if outcomes[j] else 0.0 for j in bin_indices) / count
                ece += (count / total) * abs(avg_acc - avg_conf)
                bin_details.append(
                    {
                        "bin_range": f"[{low:.1f}, {high:.1f}]",
                        "count": count,
                        "avg_confidence": round(avg_conf, 3),
                        "avg_accuracy": round(avg_acc, 3),
                    }
                )
            else:
                bin_details.append(
                    {
                        "bin_range": f"[{low:.1f}, {high:.1f}]",
                        "count": 0,
                        "avg_confidence": 0.0,
                        "avg_accuracy": 0.0,
                    }
                )

        return round(brier, 3), round(ece, 3), bin_details


def re_sub_symbols(text: str) -> str:
    """Helper to remove punctuation symbols from text for keyword extraction."""
    import re

    return re.sub(r"[^a-zA-Z0-9_\-\s]", " ", text)


_evaluation_framework_instance: EvaluationFramework | None = None


def get_evaluation_framework() -> EvaluationFramework:
    """Singleton getter for EvaluationFramework."""
    global _evaluation_framework_instance
    if _evaluation_framework_instance is None:
        _evaluation_framework_instance = EvaluationFramework()
    return _evaluation_framework_instance
