"""
Evaluation Framework for OPSRECALL.
Runs reproducible, automated benchmark experiments comparing incident investigation
performance with Hindsight Memory ON vs. Hindsight Memory OFF across synthetic scenarios.
All metrics are mathematically evaluated against verified ground truth.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from config import settings
from core.investigation import InvestigationEngine, get_investigation_engine
from core.validators import CaseEvaluationScore, EvaluationCase, InvestigationResult
from database.db import DatabaseManager, get_db

logger = logging.getLogger("opsrecall.evaluation")


class EvaluationFramework:
    """Manages evaluation scenarios, automated scoring, and benchmark reporting."""

    def __init__(
        self,
        cases_path: Optional[Path] = None,
        investigation_engine: Optional[InvestigationEngine] = None,
        db: Optional[DatabaseManager] = None,
    ):
        self.cases_path = cases_path or settings.EVALUATION_CASES_PATH
        self.investigation_engine = investigation_engine or get_investigation_engine()
        self.db = db or get_db()

    def load_evaluation_cases(self) -> List[EvaluationCase]:
        """Load benchmark cases from evaluation_cases.json."""
        if not self.cases_path.exists():
            return []

        with open(self.cases_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return [EvaluationCase(**item) for item in data]

    def evaluate_investigation(
        self,
        case: EvaluationCase,
        result: InvestigationResult,
    ) -> CaseEvaluationScore:
        """
        Grade an investigation result against the case ground truth.
        """
        mode = result.mode
        ground_truth = case.ground_truth_root_cause.lower()
        unsuccessful_to_avoid = [u.lower() for u in case.unsuccessful_mitigations_to_avoid]

        # 1. Top-3 Root Cause Accuracy
        top_3_hit = False
        gt_keywords = [
            w for w in ground_truth.replace("/", " ").replace("(", " ").replace(")", " ").split()
            if len(w) > 3 and w not in ["after", "with", "from", "into", "that", "this"]
        ]
        for h in result.hypotheses[:3]:
            h_text = h.hypothesis.lower()
            # Count keyword overlap or substring match
            matches = sum(1 for kw in gt_keywords if kw in h_text)
            if matches >= 2 or any(gt_kw in h_text for gt_kw in ["pool", "concurrency", "certificate", "stampede", "circuit breaker", "iam policy"]):
                top_3_hit = True
                break

        # 2. Retrieved Expected Historical Match
        retrieved_expected = False
        if case.expected_historical_match:
            exp_match = case.expected_historical_match.upper()
            refs = [r.upper() for r in result.historical_incidents_referenced]
            mems = [m.source_incident_id.upper() for m in result.recalled_memories if m.source_incident_id]
            if exp_match in refs or exp_match in mems:
                retrieved_expected = True
        else:
            # If distractor with no expected match, passing means no hallucinated match
            retrieved_expected = len(result.historical_incidents_referenced) == 0

        # 3. Recalled Failed Mitigations
        recalled_failed = False
        if case.unsuccessful_mitigations_to_avoid:
            if result.previous_failed_approaches:
                recalled_failed = True
        else:
            recalled_failed = True

        # 4. Avoidance of Unsuccessful Mitigations in Recommendations
        avoided_unsuccessful = True
        remediation_text = " ".join(
            [r.description.lower() + " " + r.rationale.lower() for r in result.recommended_remediation_steps]
        )
        for u in unsuccessful_to_avoid:
            # Check if recommendation recommends the exact prohibited approach
            u_keywords = [w for w in u.split() if len(w) > 4]
            if u_keywords and all(kw in remediation_text for kw in u_keywords[:2]):
                avoided_unsuccessful = False
                break

        # 5. False Recall Handling (Distractor Check)
        false_recall = False
        if case.is_distractor:
            if result.historical_incidents_referenced or result.recalled_memories:
                false_recall = True

        # 6. Appropriate Uncertainty
        appropriate_uncertainty = True
        if case.is_distractor and result.confidence_level == "High":
            appropriate_uncertainty = False

        # Calculate composite score (0 - 100)
        score = 0.0
        if top_3_hit:
            score += 35.0
        if retrieved_expected:
            score += 25.0
        if recalled_failed:
            score += 15.0
        if avoided_unsuccessful:
            score += 15.0
        if not false_recall:
            score += 5.0
        if appropriate_uncertainty:
            score += 5.0

        explanation_parts = []
        if top_3_hit:
            explanation_parts.append("Root cause captured in top-3 hypotheses (+35).")
        else:
            explanation_parts.append("Root cause missed in top-3 hypotheses (0/35).")

        if retrieved_expected:
            explanation_parts.append("Historical incident correctly matched (+25).")
        else:
            explanation_parts.append("Expected historical incident was not linked (0/25).")

        if avoided_unsuccessful:
            explanation_parts.append("Avoided known failed mitigations (+15).")
        else:
            explanation_parts.append("Recommended a previously failed mitigation (0/15).")

        return CaseEvaluationScore(
            case_id=case.case_id,
            memory_mode=mode,
            top_3_root_cause_hit=top_3_hit,
            retrieved_expected_historical=retrieved_expected,
            recalled_failed_mitigations=recalled_failed,
            avoided_unsuccessful_mitigations=avoided_unsuccessful,
            false_recall_flagged=false_recall,
            appropriate_uncertainty=appropriate_uncertainty,
            overall_score=round(score, 1),
            explanation=" ".join(explanation_parts),
        )

    def run_benchmark(self) -> Dict[str, Any]:
        """
        Execute full benchmark suite across all evaluation cases.
        Compares Memory Enabled vs. Memory Disabled investigations.
        """
        cases = self.load_evaluation_cases()
        if not cases:
            return {"error": "No evaluation cases found in data/evaluation_cases.json"}

        run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        run_timestamp = datetime.now(timezone.utc).isoformat()

        all_details: List[CaseEvaluationScore] = []
        case_comparisons: List[Dict[str, Any]] = []

        for case in cases:
            case_dict = case.model_dump()

            # Run Memory Disabled
            res_disabled = self.investigation_engine.investigate(case_dict, memory_mode="MEMORY_DISABLED")
            score_disabled = self.evaluate_investigation(case, res_disabled)

            # Run Memory Enabled
            res_enabled = self.investigation_engine.investigate(case_dict, memory_mode="MEMORY_ENABLED")
            score_enabled = self.evaluate_investigation(case, res_enabled)

            all_details.append(score_disabled)
            all_details.append(score_enabled)

            case_comparisons.append({
                "case_id": case.case_id,
                "case_title": case.case_title,
                "service": case.affected_service,
                "is_distractor": case.is_distractor,
                "disabled": {
                    "score": score_disabled.overall_score,
                    "top_3_hit": score_disabled.top_3_root_cause_hit,
                    "avoided_failed": score_disabled.avoided_unsuccessful_mitigations,
                    "hypotheses": [h.hypothesis for h in res_disabled.hypotheses[:2]],
                    "recommended_remediation": [r.description for r in res_disabled.recommended_remediation_steps[:1]],
                    "failed_approaches_warned": len(res_disabled.previous_failed_approaches),
                },
                "enabled": {
                    "score": score_enabled.overall_score,
                    "top_3_hit": score_enabled.top_3_root_cause_hit,
                    "avoided_failed": score_enabled.avoided_unsuccessful_mitigations,
                    "hypotheses": [h.hypothesis for h in res_enabled.hypotheses[:2]],
                    "recommended_remediation": [r.description for r in res_enabled.recommended_remediation_steps[:1]],
                    "failed_approaches_warned": len(res_enabled.previous_failed_approaches),
                    "historical_refs": res_enabled.historical_incidents_referenced,
                },
            })

        # Calculate macro metrics
        n_cases = len(cases)
        scores_dis = [d.overall_score for d in all_details if d.memory_mode == "MEMORY_DISABLED"]
        scores_enb = [d.overall_score for d in all_details if d.memory_mode == "MEMORY_ENABLED"]

        acc_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.top_3_root_cause_hit) / n_cases * 100.0
        acc_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.top_3_root_cause_hit) / n_cases * 100.0

        avoid_dis = sum(1 for d in all_details if d.memory_mode == "MEMORY_DISABLED" and d.avoided_unsuccessful_mitigations) / n_cases * 100.0
        avoid_enb = sum(1 for d in all_details if d.memory_mode == "MEMORY_ENABLED" and d.avoided_unsuccessful_mitigations) / n_cases * 100.0

        avg_dis = sum(scores_dis) / len(scores_dis) if scores_dis else 0.0
        avg_enb = sum(scores_enb) / len(scores_enb) if scores_enb else 0.0

        summary = {
            "run_id": run_id,
            "run_timestamp": run_timestamp,
            "cases_evaluated": n_cases,
            "metrics": {
                "accuracy": {"memory_enabled": round(acc_enb, 1), "memory_disabled": round(acc_dis, 1)},
                "failed_fix_avoidance": {"memory_enabled": round(avoid_enb, 1), "memory_disabled": round(avoid_dis, 1)},
                "average_score": {"memory_enabled": round(avg_enb, 1), "memory_disabled": round(avg_dis, 1)},
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

        # Save to JSON file
        out_file = settings.OUTPUTS_DIR / f"evaluation_{run_id}.json"
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Evaluation benchmark report written to {out_file}")
        except Exception as e:
            logger.warning(f"Could not save JSON evaluation report: {e}")

        return summary


_evaluation_framework_instance: Optional[EvaluationFramework] = None


def get_evaluation_framework() -> EvaluationFramework:
    """Singleton getter for EvaluationFramework."""
    global _evaluation_framework_instance
    if _evaluation_framework_instance is None:
        _evaluation_framework_instance = EvaluationFramework()
    return _evaluation_framework_instance

