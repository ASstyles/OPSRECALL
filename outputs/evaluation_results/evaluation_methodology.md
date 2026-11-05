# OPSRECALL — Evaluation Benchmark Methodology

## 1. Overview & Evaluation Goals

The OPSRECALL evaluation benchmark is designed to measure the objective difference that **Persistent Operational Memory** (Hindsight Cloud) introduces during production incident triage and investigation.

Traditional incident benchmarks often evaluate single-turn conversational chatbots or measure simple BLEU/ROUGE similarity against reference text. In operational engineering, however, an investigation is successful if:
1. The true root cause appears among the top actionable hypotheses.
2. The investigator is warned against repeating known **previously failed mitigations**.
3. Telemetry is correlated with recent deployment or configuration changes.
4. Novel or unrelated incidents do not trigger hallucinatory historical recall.
5. Incomplete or ambiguous evidence leads to appropriate uncertainty acknowledgment.

---

## 2. Dataset Architecture & Ground-Truth Isolation

To guarantee scientific validity and eliminate any possibility of benchmark data contamination:

- **Model-Facing Telemetry (`data/evaluation_cases.json`)**:
  Contains strictly observable operational telemetry: `case_id`, `case_title`, `affected_service`, `severity`, `symptoms`, `error_logs`, `metrics`, `recent_deployment`, and `configuration_changes`.
  **Zero answer keys, root cause labels, or scoring targets exist in this file.**
- **Evaluator-Only Ground Truth (`data/evaluation_ground_truth.json`)**:
  Contains the verified postmortem truths: `ground_truth_root_cause`, `expected_historical_match`, `unsuccessful_mitigations_to_avoid`, `is_distractor`, `requires_uncertainty`, and rubric notes.
  **This file is strictly read by the evaluation runner AFTER the model completes its investigation.**

---

## 3. The 12 Benchmark Scenarios

The suite evaluates 12 diverse scenarios across 6 operational categories:

1. **Recurrent Outages (Memory Precedent Present)**:
   - `EVAL-001` (`checkout-api`): Connection pool starvation post-Helm deploy (INC-001 match).
   - `EVAL-002` (`order-fulfillment-worker`): Worker capacity reduction post-HPA migration (INC-002 match).
   - `EVAL-003` (`payment-gateway`): Expired internal TLS certificate (INC-003 match).
   - `EVAL-004` (`catalog-service`): Cache stampede from synchronized TTLs (INC-004 match).
   - `EVAL-005` (`checkout-orchestrator`): Third-party payment gateway timeout cascade (INC-005 match).
2. **Novel Distractor Scenarios**:
   - `EVAL-006` (`cdn-edge`): S3 bucket IAM policy 403 AccessDenied (No historical precedent).
3. **Similar Symptoms with Different Underlying Causes**:
   - `EVAL-007` (`checkout-api`): Latency spike caused by PostgreSQL table lock contention during online DDL migration, NOT connection pool starvation.
4. **Unrelated Infrastructure Failure**:
   - `EVAL-008` (`auth-api`): CoreDNS cluster resolution degradation causing timeouts on internal IdP.
5. **Missing Deployment Information**:
   - `EVAL-009` (`inventory-worker`): Silent VPC MTU packet loss with zero code deployments in 7 days.
6. **Conflicting Historical Evidence**:
   - `EVAL-010` (`order-fulfillment-worker`): Worker queue backlog caused by CPU-bound vector PDF invoice rendering, NOT consumer replica deficit.
7. **Historically Inapplicable / Unsafe Fix**:
   - `EVAL-011` (`catalog-service`): Missing GIN index on jsonb attributes with cluster `NodeMemoryPressure` (>96% node memory), where scaling pods is hazardous.
8. **Novel Streaming Failure**:
   - `EVAL-012` (`event-streaming-pipeline`): Kafka consumer group rebalance storm caused by batch size exceeding `max.poll.interval.ms`.

---

## 4. Multi-Dimensional Scoring Rubric (100 Point Scale)

Each investigation is graded across 7 independent dimensions:

| Dimension | Weight | Success Criteria |
|:---|:---:|:---|
| **1. Top-3 Root Cause Accuracy** | 30 pts | True root cause captured in rank 1-3 hypotheses. |
| **2. Relevant Memory Retrieval** | 20 pts | Expected historical incident matched; or correctly omitted if novel/distractor. |
| **3. Failed-Mitigation Avoidance** | 20 pts | Recommended remediation avoids known ineffective fixes. |
| **4. Recommendation Grounding** | 15 pts | Remediation steps include concrete, actionable commands and SOPs. |
| **5. Negative Experience Recall** | 5 pts | Historical failed fixes explicitly surfaced in alert warnings. |
| **6. False Recall Resistance** | 5 pts | Zero hallucinatory historical references on novel/distractor cases. |
| **7. Appropriate Uncertainty** | 5 pts | Acknowledges uncertainty when evidence is incomplete or novel. |
| **Total** | **100 pts** | Transparent mathematical composite score. |

---

## 5. Controlled Fair Comparison

Memory OFF and Memory ON are evaluated under identical conditions:
- Identical prompt instructions (`INVESTIGATION_SYSTEM_PROMPT`).
- Identical underlying reasoning model (`openai/gpt-oss-120b`).
- Identical telemetry inputs.
- The **only** difference is that Memory ON retrieves operational experiences from Hindsight memory bank `opsrecall-demo`.
