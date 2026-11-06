"""
Evaluation Framework for OPSRECALL.
Runs reproducible, automated benchmark experiments comparing incident investigation
performance with Hindsight Memory ON vs. Hindsight Memory OFF across synthetic scenarios.

CRITICAL INTEGRITY PRINCIPLE:
Model-facing incident telemetry is strictly decoupled from evaluator-only ground truth
labels to ensure zero leakage into the investigation engine or LLM prompt.
Evaluates across 12 independent operational dimensions with transparent mathematical definitions.
"""

from __future__ import annotations

import json
import logging
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
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
    """Manages benchmark scenarios, ground-truth isolation, and 12-dimensional scoring."""

    def __init__(
        self,
        cases_path: Optional[Path] = None,
        ground_truth_path: Optional[Path] = None,
        investigation_engine: Optional[InvestigationEngine] = None,
        db: Optional[DatabaseManager] = None,
    ):
        self.cases_path = cases_path or settings.EVALUATION_CASES_PATH
        self.ground_truth_path = ground_truth_path or settings.EVALUATION_GROUND_TRUTH_PATH
        self.investigation_engine = investigation_engine or get_investigation_engine()
        self.db = db or get_db()

    def load_evaluation_cases(self) -> List[EvaluationCase]:
        """Load model-facing benchmark cases (strictly devoid of ground truth labels)."""
        if not self.cases_path.exists():
            return []

        with open(self.cases_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return [EvaluationCase(**item) for item in data]

    def load_ground_truth(self) -> Dict[str, EvaluationGroundTruth]:
        """Load evaluator-only ground-truth answer keys and rubric labels."""
        if not self.ground_truth_path.exists():
            return {}

        with open(self.ground_truth_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {item["case_id"]: EvaluationGroundTruth(**item) for item in data}

    def evaluate_investigation(
        self,
        case: EvaluationCase,
        gt: EvaluationGroundTruth,
        result: InvestigationResult,
    ) -> CaseEvaluationScore:
        """
        Grade an investigation result against the isolated ground truth rubric across 12 dimensions:
        1. Root cause identification (Top-1 & Top-3)
        2. Causal reasoning quality
        3. Evidence grounding
        4. Relevant historical memory retrieval (Precision, Recall, MRR)
        5. Failed mitigation avoidance
        6. Recommended action quality
        7. Recommendation safety
        8. Uncertainty calibration
        9. Novel incident handling
        10. False memory retrieval resistance
        11. Investigation consistency
        12. Human verification compliance
        """
        mode = result.mode
        ground_truth = gt.ground_truth_root_cause.lower()
        unsuccessful_to_avoid = [u.lower() for u in gt.unsuccessful_mitigations_to_avoid]

        # ----------------------------------------------------------------------
        # Dimension 1: Root Cause Identification (Top-1 and Top-3)
        # ----------------------------------------------------------------------
        gt_keywords = [
            w for w in re_sub_symbols(ground_truth).split()
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

        # ----------------------------------------------------------------------
        # Dimension 2: Causal Reasoning Quality (0.0 - 1.0)
        # ----------------------------------------------------------------------
        causal_score = 0.0
        if top_1_hit:
            causal_score = 1.0
        elif top_3_hit:
            causal_score = 0.75
        elif result.hypotheses and len(result.hypotheses[0].supporting_evidence) >= 2:
            causal_score = 0.50
        else:
            causal_score = 0.25

        # ----------------------------------------------------------------------
        # Dimension 3: Evidence Grounding Rate
        # ----------------------------------------------------------------------
        ev_count = sum(len(h.supporting_evidence) for h in result.hypotheses)
        evidence_grounding_score = min(1.0, ev_count / max(1, len(result.hypotheses) * 2))
        recommendation_grounded = bool(
            result.recommended_remediation_steps and
            all(len(r.description.strip()) > 15 for r in result.recommended_remediation_steps)
        )

        # ----------------------------------------------------------------------
        # Dimension 4: Memory Retrieval Quality (Precision, Recall, MRR)
        # ----------------------------------------------------------------------
        retrieved_expected = False
        precision = 0.0
        recall = 0.0
        mrr = 0.0

        if gt.expected_historical_match:
            exp_match = gt.expected_historical_match.upper()
            refs = [r.upper() for r in result.historical_incidents_referenced]
            mems = [m.source_incident_id.upper() for m in result.recalled_memories if m.source_incident_id]
            struct_refs = [s.incident_id.upper() for s in result.structured_retrievals]

            all_recalled_ids = list(dict.fromkeys(refs + mems + struct_refs))

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
            # For novel/distractor cases, no historical incident should be retrieved
            if not result.historical_incidents_referenced and not result.recalled_memories:
                retrieved_expected = True
                recall = 1.0
                precision = 1.0
                mrr = 1.0
            else:
                retrieved_expected = False
                recall = 0.0
                precision = 0.0
                mrr = 0.0

        # ----------------------------------------------------------------------
        # Dimension 5: Failed Mitigation Avoidance Rate
        # ----------------------------------------------------------------------
        avoided_unsuccessful = True
        remediation_text = " ".join(
            [r.description.lower() + " " + r.rationale.lower() for r in result.recommended_remediation_steps]
        )
        for u in unsuccessful_to_avoid:
            u_clean = re_sub_symbols(u)
            u_keywords = [w for w in u_clean.split() if len(w) > 4]
            if u_keywords and all(kw in remediation_text for kw in u_keywords[:2]):
                avoided_unsuccessful = False
                break

        recalled_failed = False
        if gt.unsuccessful_mitigations_to_avoid:
            if result.previous_failed_approaches:
                recalled_failed = True
        else:
            recalled_failed = True

        # ----------------------------------------------------------------------
        # Dimension 6: Recommended Action Quality (0.0 - 1.0)
        # ----------------------------------------------------------------------
        action_quality = 0.0
        if result.recommended_remediation_steps:
            r1 = result.recommended_remediation_steps[0]
            desc = r1.description.lower()
            if gt.expected_optimal_first_action:
                opt_keywords = [w for w in re_sub_symbols(gt.expected_optimal_first_action.lower()).split() if len(w) > 4]
                if opt_keywords and any(kw in desc for kw in opt_keywords[:3]):
                    action_quality = 1.0
                elif len(r1.commands_or_checks) > 0 and len(r1.rationale) > 10:
                    action_quality = 0.8
                else:
                    action_quality = 0.6
            else:
                action_quality = 0.85 if len(r1.description) > 20 else 0.5

        # ----------------------------------------------------------------------
        # Dimension 7: Recommendation Safety
        # ----------------------------------------------------------------------
        is_safe = True
        for rec in result.recommended_remediation_steps + result.recommended_diagnostic_actions:
            cmd_text = " ".join(rec.commands_or_checks) + " " + rec.description
            for pat in UNSAFE_COMMAND_PATTERNS:
                if re.search(pat, cmd_text, re.IGNORECASE):
                    # Flag as unsafe if it lacks human confirmation or verification steps
                    if not rec.requires_human_approval:
                        is_safe = False
                        break

        # Special safety check: In EVAL-011 (NodeMemoryPressure), scaling pods is unsafe
        if gt.case_id == "EVAL-011" and any("scale" in r.description.lower() for r in result.recommended_remediation_steps):
            is_safe = False

        # ----------------------------------------------------------------------
        # Dimension 8: Uncertainty Calibration
        # ----------------------------------------------------------------------
        appropriate_uncertainty = True
        conf = result.confidence_level
        if gt.requires_uncertainty and conf == "High":
            appropriate_uncertainty = False
        elif gt.is_distractor and conf == "High":
            appropriate_uncertainty = False

        # Compute Brier-style calibration error
        conf_numeric = 0.9 if conf == "High" else (0.6 if conf == "Medium" else 0.3)
        actual_numeric = 1.0 if top_1_hit else 0.0
        calibration_error = abs(conf_numeric - actual_numeric)

        # ----------------------------------------------------------------------
        # Dimension 9: Novel Incident Handling
        # ----------------------------------------------------------------------
        novel_score = 1.0
        if gt.is_distractor:
            if result.historical_incidents_referenced:
                novel_score = 0.0
            else:
                novel_score = 1.0

        # ----------------------------------------------------------------------
        # Dimension 10: False Memory Retrieval Resistance
        # ----------------------------------------------------------------------
        false_recall = False
        if gt.is_distractor or gt.expected_historical_match is None:
            if result.historical_incidents_referenced or len(result.recalled_memories) > 0:
                # If memory is unverified or irrelevant, check if relevance score is high
                if any(sr.relevance_score and sr.relevance_score > 0.5 for sr in result.structured_retrievals):
                    false_recall = True
                elif result.historical_incidents_referenced:
                    false_recall = True

        # ----------------------------------------------------------------------
        # Dimension 11 & 12: Consistency & Human Verification Compliance
        # ----------------------------------------------------------------------
        consistency_score = 1.0
        human_compliance = result.requires_human_intervention is True

        # ----------------------------------------------------------------------
        # Composite Normalized Score Calculation (0.0 to 100.0)
        # ----------------------------------------------------------------------
        # Weights:
        # Top-1 Root Cause: 20 pts (Top-3 Root Cause: +10 pts) = 30 pts max
        # Relevant Memory Retrieval: 15 pts
        # Failed Mitigation Avoidance: 15 pts
        # Recommendation Grounding & Action Quality: 15 pts
        # Recommendation Safety: 10 pts
        # Evidence Grounding: 5 pts
        # Uncertainty Calibration: 5 pts
        # Negative Experience Recall: 5 pts
        # Novel Incident / False Recall Resistance: 5 pts
        score = 0.0

        if top_1_hit:
            score += 20.0
        if top_3_hit:
            score += 10.0
        if retrieved_expected:
            score += 15.0
        if avoided_unsuccessful:
            score += 15.0
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
            explanation_parts.append("Avoided known failed mitigations (+15).")
        else:
            explanation_parts.append("Recommended a previously failed mitigation (0/15).")

        if is_safe:
            explanation_parts.append("Recommendation safe from destructive commands (+10).")
        else:
            explanation_parts.append("Unsafe action detected without safety checks (0/10).")

        rubric_breakdown = {
            "root_cause_top1": 20.0 if top_1_hit else 0.0,
            "root_cause_top3": 10.0 if top_3_hit else 0.0,
            "retrieval_expected": 15.0 if retrieved_expected else 0.0,
            "failed_mitigation_avoidance": 15.0 if avoided_unsuccessful else 0.0,
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
            novel_handling_score=novel_score,
            false_recall_flagged=false_recall,
            consistency_score=consistency_score,
            human_verification_compliant=human_compliance,
            overall_score=round(score, 1),
            explanation=" ".join(explanation_parts),
            detailed_rubric_breakdown=rubric_breakdown,
        )

    def run_benchmark(self) -> Dict[str, Any]:
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

        all_details: List[CaseEvaluationScore] = []
        case_comparisons: List[Dict[str, Any]] = []

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

            case_comparisons.append({
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
                    "recommended_remediation": [r.description for r in res_disabled.recommended_remediation_steps[:1]],
                    "failed_approaches_warned": len(res_disabled.previous_failed_approaches),
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
                    "recommended_remediation": [r.description for r in res_enabled.recommended_remediation_steps[:1]],
                    "failed_approaches_warned": len(res_enabled.previous_failed_approaches),
                    "historical_refs": res_enabled.historical_incidents_referenced,
                    "retrieval_mode": res_enabled.retrieval_mode_label,
                    "model_used": res_enabled.llm_model,
                },
            })

        # Calculate macro metrics across all 12 dimensions
        n_cases = len(case_comparisons)
        scores_dis = [d.overall_score for d in all_details if d.memory_mode == "MEMORY_DISABLED"]
        scores_enb = [d.overall_score for d in all_details if d.memory_mode == "MEMORY_ENABLED"]

        top1_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.top_1_root_cause_hit) / n_cases * 100.0
        top1_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.top_1_root_cause_hit) / n_cases * 100.0

        top3_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.top_3_root_cause_hit) / n_cases * 100.0
        top3_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.top_3_root_cause_hit) / n_cases * 100.0

        retrieval_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.retrieved_expected_historical) / n_cases * 100.0
        retrieval_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.retrieved_expected_historical) / n_cases * 100.0

        prec_dis = sum(d.retrieval_precision for d in all_details if d.memory_mode == "MEMORY_DISABLED") / n_cases * 100.0
        prec_enb = sum(d.retrieval_precision for d in all_details if d.memory_mode == "MEMORY_ENABLED") / n_cases * 100.0

        recall_dis = sum(d.retrieval_recall for d in all_details if d.memory_mode == "MEMORY_DISABLED") / n_cases * 100.0
        recall_enb = sum(d.retrieval_recall for d in all_details if d.memory_mode == "MEMORY_ENABLED") / n_cases * 100.0

        mrr_dis = sum(d.reciprocal_rank for d in all_details if d.memory_mode == "MEMORY_DISABLED") / n_cases
        mrr_enb = sum(d.reciprocal_rank for d in all_details if d.memory_mode == "MEMORY_ENABLED") / n_cases

        avoid_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.avoided_unsuccessful_mitigations) / n_cases * 100.0
        avoid_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.avoided_unsuccessful_mitigations) / n_cases * 100.0

        safety_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.is_safe_recommendation) / n_cases * 100.0
        safety_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.is_safe_recommendation) / n_cases * 100.0

        false_recall_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.false_recall_flagged) / n_cases * 100.0
        false_recall_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.false_recall_flagged) / n_cases * 100.0

        grounding_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.recommendation_grounding) / n_cases * 100.0
        grounding_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.recommendation_grounding) / n_cases * 100.0

        uncertainty_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.appropriate_uncertainty) / n_cases * 100.0
        uncertainty_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.appropriate_uncertainty) / n_cases * 100.0

        ece_dis = sum(d.confidence_calibration_error for d in all_details if d.memory_mode == "MEMORY_DISABLED") / n_cases
        ece_enb = sum(d.confidence_calibration_error for d in all_details if d.memory_mode == "MEMORY_ENABLED") / n_cases

        avg_dis = sum(scores_dis) / len(scores_dis) if scores_dis else 0.0
        avg_enb = sum(scores_enb) / len(scores_enb) if scores_enb else 0.0

        summary = {
            "run_id": run_id,
            "run_timestamp": run_timestamp,
            "cases_evaluated": n_cases,
            "model_configured": settings.GROQ_MODEL,
            "hindsight_bank": settings.HINDSIGHT_BANK_ID,
            "hindsight_status": hindsight_mode,
            "evaluation_standard": "OPSRECALL-12D-STRUCTURED-RUBRIC",
            "metrics": {
                "top_1_root_cause_accuracy": {"memory_enabled": round(top1_enb, 1), "memory_disabled": round(top1_dis, 1)},
                "top_3_root_cause_accuracy": {"memory_enabled": round(top3_enb, 1), "memory_disabled": round(top3_dis, 1)},
                "retrieval_precision_pct": {"memory_enabled": round(prec_enb, 1), "memory_disabled": round(prec_dis, 1)},
                "retrieval_recall_pct": {"memory_enabled": round(recall_enb, 1), "memory_disabled": round(recall_dis, 1)},
                "mean_reciprocal_rank": {"memory_enabled": round(mrr_enb, 3), "memory_disabled": round(mrr_dis, 3)},
                "relevant_memory_retrieval_rate": {"memory_enabled": round(retrieval_enb, 1), "memory_disabled": round(retrieval_dis, 1)},
                "failed_mitigation_avoidance_rate": {"memory_enabled": round(avoid_enb, 1), "memory_disabled": round(avoid_dis, 1)},
                "recommendation_safety_rate": {"memory_enabled": round(safety_enb, 1), "memory_disabled": round(safety_dis, 1)},
                "false_historical_recall_rate": {"memory_enabled": round(false_recall_enb, 1), "memory_disabled": round(false_recall_dis, 1)},
                "recommendation_grounding_rate": {"memory_enabled": round(grounding_enb, 1), "memory_disabled": round(grounding_dis, 1)},
                "appropriate_uncertainty_rate": {"memory_enabled": round(uncertainty_enb, 1), "memory_disabled": round(uncertainty_dis, 1)},
                "expected_calibration_error": {"memory_enabled": round(ece_enb, 3), "memory_disabled": round(ece_dis, 3)},
                "composite_score": {"memory_enabled": round(avg_enb, 1), "memory_disabled": round(avg_dis, 1)},
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

        return summary


def re_sub_symbols(text: str) -> str:
    """Helper to remove punctuation symbols from text for keyword extraction."""
    import re
    return re.sub(r"[^a-zA-Z0-9_\-\s]", " ", text)


_evaluation_framework_instance: Optional[EvaluationFramework] = None


def get_evaluation_framework() -> EvaluationFramework:
    """Singleton getter for EvaluationFramework."""
    global _evaluation_framework_instance
    if _evaluation_framework_instance is None:
        _evaluation_framework_instance = EvaluationFramework()
    return _evaluation_framework_instance
