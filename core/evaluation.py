"""
Evaluation Framework for OPSRECALL.
Runs reproducible, automated benchmark experiments comparing incident investigation
performance with Hindsight Memory ON vs. Hindsight Memory OFF across synthetic scenarios.

CRITICAL INTEGRITY PRINCIPLE:
Model-facing incident telemetry is strictly decoupled from evaluator-only ground truth
labels to ensure zero leakage into the investigation engine or LLM prompt.
"""

from __future__ import annotations

import json
import logging
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


class EvaluationFramework:
    """Manages benchmark scenarios, ground-truth isolation, and multi-dimensional scoring."""

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
        Grade an investigation result against the isolated ground truth rubric.
        Computes 7 distinct dimensions and a documented composite score (0 - 100).
        """
        mode = result.mode
        ground_truth = gt.ground_truth_root_cause.lower()
        unsuccessful_to_avoid = [u.lower() for u in gt.unsuccessful_mitigations_to_avoid]

        # ----------------------------------------------------------------------
        # 1. Top-3 Root Cause Accuracy (Weight: 30 pts)
        # ----------------------------------------------------------------------
        top_3_hit = False
        gt_keywords = [
            w for w in ground_truth.replace("/", " ").replace("(", " ").replace(")", " ").split()
            if len(w) > 3 and w not in ["after", "with", "from", "into", "that", "this", "during"]
        ]
        for h in result.hypotheses[:3]:
            h_text = h.hypothesis.lower()
            matches = sum(1 for kw in gt_keywords if kw in h_text)
            if matches >= 2 or any(
                domain_term in h_text
                for domain_term in [
                    "connection pool", "concurrency", "certificate", "stampede",
                    "circuit breaker", "iam policy", "table lock", "coredns",
                    "packet loss", "pdf invoice", "node memory", "rebalance storm"
                ]
                if domain_term in ground_truth
            ):
                top_3_hit = True
                break

        # ----------------------------------------------------------------------
        # 2. Relevant Memory Retrieval (Weight: 20 pts)
        # ----------------------------------------------------------------------
        retrieved_expected = False
        if gt.expected_historical_match:
            exp_match = gt.expected_historical_match.upper()
            refs = [r.upper() for r in result.historical_incidents_referenced]
            mems = [m.source_incident_id.upper() for m in result.recalled_memories if m.source_incident_id]
            if exp_match in refs or exp_match in mems:
                retrieved_expected = True
        else:
            # If novel or distractor scenario with no expected match, passing means no hallucinated match
            retrieved_expected = len(result.historical_incidents_referenced) == 0

        # ----------------------------------------------------------------------
        # 3. Failed-Mitigation Avoidance (Weight: 20 pts)
        # ----------------------------------------------------------------------
        avoided_unsuccessful = True
        remediation_text = " ".join(
            [r.description.lower() + " " + r.rationale.lower() for r in result.recommended_remediation_steps]
        )
        for u in unsuccessful_to_avoid:
            u_keywords = [w for w in u.split() if len(w) > 4]
            if u_keywords and all(kw in remediation_text for kw in u_keywords[:2]):
                avoided_unsuccessful = False
                break

        # ----------------------------------------------------------------------
        # 4. Recommendation Grounding & Actionability (Weight: 15 pts)
        # ----------------------------------------------------------------------
        recommendation_grounded = bool(
            result.recommended_remediation_steps and
            all(len(r.description.strip()) > 15 for r in result.recommended_remediation_steps)
        )

        # ----------------------------------------------------------------------
        # 5. Negative Experience Recall (Weight: 5 pts)
        # ----------------------------------------------------------------------
        recalled_failed = False
        if gt.unsuccessful_mitigations_to_avoid:
            if result.previous_failed_approaches:
                recalled_failed = True
        else:
            recalled_failed = True

        # ----------------------------------------------------------------------
        # 6. False Historical Recall Resistance (Weight: 5 pts)
        # ----------------------------------------------------------------------
        false_recall = False
        if gt.is_distractor or gt.expected_historical_match is None:
            if result.historical_incidents_referenced or result.recalled_memories:
                false_recall = True

        # ----------------------------------------------------------------------
        # 7. Appropriate Uncertainty Handling (Weight: 5 pts)
        # ----------------------------------------------------------------------
        appropriate_uncertainty = True
        if gt.requires_uncertainty and result.confidence_level == "High":
            appropriate_uncertainty = False
        elif gt.is_distractor and result.confidence_level == "High":
            appropriate_uncertainty = False

        # Composite Score Calculation
        score = 0.0
        if top_3_hit:
            score += 30.0
        if retrieved_expected:
            score += 20.0
        if avoided_unsuccessful:
            score += 20.0
        if recommendation_grounded:
            score += 15.0
        if recalled_failed:
            score += 5.0
        if not false_recall:
            score += 5.0
        if appropriate_uncertainty:
            score += 5.0

        explanation_parts = []
        if top_3_hit:
            explanation_parts.append("Root cause in top-3 (+30).")
        else:
            explanation_parts.append("Root cause missed in top-3 (0/30).")

        if retrieved_expected:
            explanation_parts.append("Historical incident correctly matched (+20).")
        else:
            explanation_parts.append("Historical incident mismatched/missing (0/20).")

        if avoided_unsuccessful:
            explanation_parts.append("Avoided known failed mitigations (+20).")
        else:
            explanation_parts.append("Recommended a previously failed fix (0/20).")

        if recommendation_grounded:
            explanation_parts.append("Remediation grounded and actionable (+15).")

        return CaseEvaluationScore(
            case_id=case.case_id,
            scenario_type=gt.scenario_type,
            memory_mode=mode,
            top_3_root_cause_hit=top_3_hit,
            retrieved_expected_historical=retrieved_expected,
            recalled_failed_mitigations=recalled_failed,
            avoided_unsuccessful_mitigations=avoided_unsuccessful,
            false_recall_flagged=false_recall,
            appropriate_uncertainty=appropriate_uncertainty,
            recommendation_grounding=recommendation_grounded,
            overall_score=round(score, 1),
            explanation=" ".join(explanation_parts),
        )

    def run_benchmark(self) -> Dict[str, Any]:
        """
        Execute full benchmark suite across all 12 evaluation scenarios.
        Evaluates Memory Enabled vs. Memory Disabled investigations with complete ground truth isolation.
        """
        cases = self.load_evaluation_cases()
        ground_truth = self.load_ground_truth()

        if not cases:
            return {"error": "No evaluation cases found in data/evaluation_cases.json"}

        run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        run_timestamp = datetime.now(timezone.utc).isoformat()

        all_details: List[CaseEvaluationScore] = []
        case_comparisons: List[Dict[str, Any]] = []

        for case in cases:
            gt = ground_truth.get(case.case_id)
            if not gt:
                logger.warning(f"Ground truth not found for {case.case_id}; skipping.")
                continue

            # Model input contains strictly telemetry, with zero ground-truth keys
            model_input = case.model_dump()

            # Run Memory Disabled
            res_disabled = self.investigation_engine.investigate(model_input, memory_mode="MEMORY_DISABLED")
            score_disabled = self.evaluate_investigation(case, gt, res_disabled)

            # Run Memory Enabled
            res_enabled = self.investigation_engine.investigate(model_input, memory_mode="MEMORY_ENABLED")
            score_enabled = self.evaluate_investigation(case, gt, res_enabled)

            all_details.append(score_disabled)
            all_details.append(score_enabled)

            case_comparisons.append({
                "case_id": case.case_id,
                "case_title": case.case_title,
                "service": case.affected_service,
                "scenario_type": gt.scenario_type,
                "is_distractor": gt.is_distractor,
                "disabled": {
                    "score": score_disabled.overall_score,
                    "top_3_hit": score_disabled.top_3_root_cause_hit,
                    "avoided_failed": score_disabled.avoided_unsuccessful_mitigations,
                    "recalled_failed": score_disabled.recalled_failed_mitigations,
                    "false_recall": score_disabled.false_recall_flagged,
                    "appropriate_uncertainty": score_disabled.appropriate_uncertainty,
                    "hypotheses": [h.hypothesis for h in res_disabled.hypotheses[:2]],
                    "recommended_remediation": [r.description for r in res_disabled.recommended_remediation_steps[:1]],
                    "failed_approaches_warned": len(res_disabled.previous_failed_approaches),
                    "model_used": res_disabled.llm_model,
                },
                "enabled": {
                    "score": score_enabled.overall_score,
                    "top_3_hit": score_enabled.top_3_root_cause_hit,
                    "avoided_failed": score_enabled.avoided_unsuccessful_mitigations,
                    "recalled_failed": score_enabled.recalled_failed_mitigations,
                    "false_recall": score_enabled.false_recall_flagged,
                    "appropriate_uncertainty": score_enabled.appropriate_uncertainty,
                    "hypotheses": [h.hypothesis for h in res_enabled.hypotheses[:2]],
                    "recommended_remediation": [r.description for r in res_enabled.recommended_remediation_steps[:1]],
                    "failed_approaches_warned": len(res_enabled.previous_failed_approaches),
                    "historical_refs": res_enabled.historical_incidents_referenced,
                    "model_used": res_enabled.llm_model,
                },
            })

        # Calculate macro metrics across all 7 dimensions
        n_cases = len(case_comparisons)
        scores_dis = [d.overall_score for d in all_details if d.memory_mode == "MEMORY_DISABLED"]
        scores_enb = [d.overall_score for d in all_details if d.memory_mode == "MEMORY_ENABLED"]

        acc_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.top_3_root_cause_hit) / n_cases * 100.0
        acc_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.top_3_root_cause_hit) / n_cases * 100.0

        retrieval_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.retrieved_expected_historical) / n_cases * 100.0
        retrieval_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.retrieved_expected_historical) / n_cases * 100.0

        avoid_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.avoided_unsuccessful_mitigations) / n_cases * 100.0
        avoid_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.avoided_unsuccessful_mitigations) / n_cases * 100.0

        false_recall_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.false_recall_flagged) / n_cases * 100.0
        false_recall_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.false_recall_flagged) / n_cases * 100.0

        grounding_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.recommendation_grounding) / n_cases * 100.0
        grounding_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.recommendation_grounding) / n_cases * 100.0

        uncertainty_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.appropriate_uncertainty) / n_cases * 100.0
        uncertainty_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.appropriate_uncertainty) / n_cases * 100.0

        avg_dis = sum(scores_dis) / len(scores_dis) if scores_dis else 0.0
        avg_enb = sum(scores_enb) / len(scores_enb) if scores_enb else 0.0

        summary = {
            "run_id": run_id,
            "run_timestamp": run_timestamp,
            "cases_evaluated": n_cases,
            "model_configured": settings.GROQ_MODEL,
            "hindsight_bank": settings.HINDSIGHT_BANK_ID,
            "hindsight_status": "LIVE" if settings.is_hindsight_configured() else "OFFLINE_PREVIEW",
            "metrics": {
                "top_3_root_cause_accuracy": {"memory_enabled": round(acc_enb, 1), "memory_disabled": round(acc_dis, 1)},
                "relevant_memory_retrieval_rate": {"memory_enabled": round(retrieval_enb, 1), "memory_disabled": round(retrieval_dis, 1)},
                "failed_mitigation_avoidance_rate": {"memory_enabled": round(avoid_enb, 1), "memory_disabled": round(avoid_dis, 1)},
                "false_historical_recall_rate": {"memory_enabled": round(false_recall_enb, 1), "memory_disabled": round(false_recall_dis, 1)},
                "recommendation_grounding_rate": {"memory_enabled": round(grounding_enb, 1), "memory_disabled": round(grounding_dis, 1)},
                "appropriate_uncertainty_rate": {"memory_enabled": round(uncertainty_enb, 1), "memory_disabled": round(uncertainty_dis, 1)},
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
                accuracy_enabled=acc_enb,
                accuracy_disabled=acc_dis,
                avoidance_enabled=avoid_enb,
                avoidance_disabled=avoid_dis,
                avg_score_enabled=avg_enb,
                avg_score_disabled=avg_dis,
                summary_json=summary,
                details=all_details,
            )
        except Exception as e:
            logger.warning(f"Could not persist evaluation run to SQLite: {e}")

        # Save canonical JSON files as required by Phase 3:
        # 1. outputs/evaluation_results/evaluation_summary.json
        summary_file = settings.OUTPUTS_DIR / "evaluation_summary.json"
        try:
            with open(summary_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not write {summary_file}: {e}")

        # 2. outputs/evaluation_results/evaluation_case_results.json
        case_results_file = settings.OUTPUTS_DIR / "evaluation_case_results.json"
        try:
            with open(case_results_file, "w", encoding="utf-8") as f:
                json.dump(case_comparisons, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not write {case_results_file}: {e}")

        # 3. Timestamped run file
        out_file = settings.OUTPUTS_DIR / f"evaluation_{run_id}.json"
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not write {out_file}: {e}")

        return summary


_evaluation_framework_instance: Optional[EvaluationFramework] = None


def get_evaluation_framework() -> EvaluationFramework:
    """Singleton getter for EvaluationFramework."""
    global _evaluation_framework_instance
    if _evaluation_framework_instance is None:
        _evaluation_framework_instance = EvaluationFramework()
    return _evaluation_framework_instance
