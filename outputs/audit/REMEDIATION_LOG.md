# OPSRECALL — Engineering Remediation Log

This document records all engineering remediations applied to OPSRECALL during the final technical audit and competition readiness hardening.

---

## Remediation Summary

| ID | Priority | Category | Component | Status | Verification |
|---|---|---|---|---|---|
| **REM-P0-1** | P0 | LLM Availability | `config.py`, `core/llm_engine.py`, `.env.example` | **RESOLVED** | `scripts/verify_groq.py` |
| **REM-P0-2** | P0 | Evaluation Integrity | `data/evaluation_cases.json`, `data/evaluation_ground_truth.json`, `core/evaluation.py` | **RESOLVED** | Benchmark tests & isolation inspection |
| **REM-P1-1** | P1 | Hindsight Test Bank Isolation | `core/hindsight_client.py`, `scripts/verify_hindsight.py`, `tests/test_live_integration.py` | **RESOLVED** | `scripts/verify_hindsight.py` & pytest |
| **REM-P1-2** | P1 | Benchmark Realism & Scope | `data/evaluation_cases.json`, `core/evaluation.py`, `core/llm_engine.py` | **RESOLVED** | 12-case benchmark execution |
| **REM-P1-3** | P1 | Multi-Dimensional Evaluation Metrics | `core/validators.py`, `core/evaluation.py`, `scripts/run_evaluation.py` | **RESOLVED** | 7-dimension macro metric suite |
| **REM-P2-1** | P2 | Learning Engine Input Validation | `core/learning_engine.py`, `tests/test_learning.py` | **RESOLVED** | Pytest validation error tests |
| **REM-P2-2** | P2 | Streamlit Offline Memory Preview Signature | `core/investigation.py`, `app.py`, `tests/test_ui.py` | **RESOLVED** | `tests/test_ui.py` headless Streamlit |

---

## Detailed Remediation Entries

### REM-P0-1: Groq Model Migration from Deprecated Model to `openai/gpt-oss-120b`
- **Issue**: Groq announced deprecation of `llama-3.3-70b-versatile` with sunset effective August 16, 2026 for free/developer tiers. Defaulting to this model risked sudden API 404/410 failures.
- **Files Modified**:
  - `config.py`
  - `.env.example`
  - `core/llm_engine.py`
  - `scripts/verify_groq.py` (new)
  - `outputs/audit/GROQ_MODEL_MIGRATION.md` (new)
- **Remediation**:
  1. Updated `config.py` default `GROQ_MODEL` to `openai/gpt-oss-120b` (131,072 context window, MoE architecture, native structured JSON mode).
  2. Implemented dynamic fallback cascade in `core/llm_engine.py`: primary `openai/gpt-oss-120b` -> fallback `llama-3.3-70b-versatile` -> lightweight `llama-3.1-8b-instant`.
  3. Replaced silent fallback to offline mode on API error with explicit logging and fail-fast exceptions (`LLMGenerationError`), ensuring failed live calls do not silently report dummy telemetry.
  4. Added `_sanitize_telemetry()` to guarantee zero ground truth or evaluation labels reach prompt payloads.
  5. Built `scripts/verify_groq.py` to probe account model availability via `GET https://api.groq.com/openai/v1/models` and test JSON mode chat completions.
- **Verification**:
  - `scripts/verify_groq.py` verifies error handling and model configuration without credential leaks.
  - `tests/test_live_integration.py::test_live_groq_generation_structured_json` validates live inference when keys are provided.

---

### REM-P0-2: Ground Truth Isolation & Anti-Leakage Decoupling
- **Issue**: `evaluation_cases.json` previously merged input symptoms with evaluator labels (`ground_truth_root_cause`, `ground_truth_failed_fix`, `optimal_first_action`) in a single JSON structure. This posed a critical data leakage vulnerability.
- **Files Modified**:
  - `data/evaluation_cases.json`
  - `data/evaluation_ground_truth.json` (new)
  - `core/validators.py`
  - `core/evaluation.py`
  - `outputs/audit/EVALUATION_INTEGRITY_REPORT.md` (new)
  - `outputs/evaluation_results/evaluation_methodology.md` (new)
- **Remediation**:
  1. Purged all ground truth fields from `data/evaluation_cases.json`. The file now strictly contains model-facing inputs: `case_id`, `incident_type`, `service_name`, `severity`, `symptoms`, `error_logs`, `metrics_snapshot`, `deployment_change`, `notes`.
  2. Created `data/evaluation_ground_truth.json` containing evaluator-only rubrics: `ground_truth_root_cause`, `ground_truth_failed_fix`, `optimal_first_action`, `acceptable_hypotheses`, `anti_patterns_to_avoid`.
  3. In `core/validators.py`, declared separate Pydantic models: `EvaluationCase` (pure telemetry) and `EvaluationGroundTruth` (evaluation answer key).
  4. In `core/evaluation.py`, refactored evaluation pipeline: model/investigation engine receives solely `EvaluationCase` instances. Evaluation engine loads `EvaluationGroundTruth` independently and computes metrics by scoring predictions against the isolated answer key.
- **Verification**:
  - `tests/test_evaluation.py::test_load_evaluation_cases_isolated` asserts no ground truth keys exist in test input.
  - `tests/test_evaluation.py::test_load_ground_truth_isolated` verifies ground truth exists only in the evaluator file.

---

### REM-P1-1: Hindsight Test Bank Isolation & Live Verification Suite
- **Issue**: The application used a single production/demo bank (`opsrecall-demo`) for all operations, which risked pollutive cross-talk during automated test runs.
- **Files Modified**:
  - `config.py`
  - `.env.example`
  - `core/hindsight_client.py`
  - `scripts/verify_hindsight.py`
  - `tests/test_live_integration.py`
  - `outputs/audit/HINDSIGHT_LIVE_VERIFICATION.md` (new)
- **Remediation**:
  1. Added `HINDSIGHT_TEST_BANK_ID=opsrecall-live-tests` in `config.py` and `.env.example`.
  2. Added `test_bank_id` property and bounded asynchronous processing poller `wait_for_document_processing(bank_id, document_id, timeout_sec)` in `core/hindsight_client.py`.
  3. Implemented deterministic idempotency via `document_id="incident-" + incident_id`.
  4. Updated `scripts/verify_hindsight.py` with a 10-step cloud verification suite operating strictly against `opsrecall-live-tests`.
  5. Updated live integration tests in `tests/test_live_integration.py` to target the test bank.
- **Verification**:
  - `tests/test_memory.py` passes all unit tests for Hindsight formatting, queries, and error handling.
  - `tests/test_live_integration.py` safely skips when live credentials are not set and targets `opsrecall-live-tests` when set.

---

### REM-P1-2 & REM-P1-3: Benchmark Expansion to 12 Cases & 7 Evaluation Dimensions
- **Issue**: The original evaluation suite consisted of only 6 synthetic cases (5 historical variants + 1 distractor), reporting a single composite score without granular diagnostic metrics.
- **Files Modified**:
  - `data/evaluation_cases.json`
  - `data/evaluation_ground_truth.json`
  - `core/validators.py`
  - `core/evaluation.py`
  - `core/llm_engine.py`
  - `scripts/run_evaluation.py`
  - `tests/test_evaluation.py`
- **Remediation**:
  1. Expanded benchmark dataset from 6 to 12 cases:
     - EVAL-001 through EVAL-005: Core recurrent operational outages.
     - EVAL-006: Novel distractor incident (unrelated novel issue).
     - EVAL-007: Conflicting telemetry (HTTP 502/504 edge timeout vs DB connection spike).
     - EVAL-008: Same symptom (HTTP 500), different root cause (token signing key vs DB).
     - EVAL-009: Missing deployment event (configuration drift / background exhaustion).
     - EVAL-010: Outdated/unsafe historical fix (scaling replicas worsens DB connection storm).
     - EVAL-011: Multi-service cascade (`checkout-api` failure induces upstream `cart-service` memory leak).
     - EVAL-012: Novel streaming rebalance storm (`inventory-worker` consumer group crash loop).
  2. Expanded evaluation metrics from 1 composite score to 7 rigorous dimensions:
     - `top_1_root_cause_accuracy`
     - `top_3_root_cause_accuracy`
     - `failed_mitigation_avoidance_rate`
     - `optimal_action_precision`
     - `confidence_calibration_error`
     - `evidence_grounding_score`
     - `relevance_retrieval_rate`
  3. Fixed rule-based matching precedence bug in `core/llm_engine.py` where generic pool search preempted orchestrator logic.
- **Verification**:
  - Evaluator run on 12 cases outputs full statistical breakdown in `outputs/evaluation_results/evaluation_summary.json` and `evaluation_case_results.json`.
  - `python -m pytest tests/test_evaluation.py` passes 100%.

---

### REM-P2-1: Learning Engine Robust Input Validation
- **Issue**: `LearningEngine.confirm_and_retain_resolution()` did not reject empty or whitespace-only strings for root cause and resolution description, which could allow empty memory submissions.
- **Files Modified**:
  - `core/learning_engine.py`
  - `tests/test_learning.py`
- **Remediation**:
  1. Added explicit strip-and-validate checks in `core/learning_engine.py` for `root_cause`, `resolution_description`, and `incident_id`.
  2. Added unit tests in `tests/test_learning.py::test_confirm_resolution_validation_errors` asserting `ValueError` is raised on empty strings.
- **Verification**:
  - `python -m pytest tests/test_learning.py` passes all test cases.

---

### REM-P2-2: Streamlit Offline Memory Explorer Compatibility
- **Issue**: Calling `_get_offline_preview_memories()` required `deployment_change` as a positional parameter, causing a `TypeError` in `app.py` line 603 when invoked with fewer parameters.
- **Files Modified**:
  - `core/investigation.py`
  - `app.py`
  - `tests/test_ui.py`
- **Remediation**:
  1. Changed `_get_offline_preview_memories(service, symptoms=None, error_logs=None, deployment_change=None)` to accept optional default parameters.
  2. Updated `app.py` call site to supply explicit arguments for realistic memory inspection.
  3. Verified headless Streamlit test suite across all 7 UI navigation targets (`Command Center`, `Incident Console`, `Investigation & Comparison`, `Memory Explorer`, `Learning Center`, `Evaluation Lab`, `Architecture & System Docs`).
- **Verification**:
  - `python -m pytest tests/test_ui.py` passes 100% (7/7 tests passed).
