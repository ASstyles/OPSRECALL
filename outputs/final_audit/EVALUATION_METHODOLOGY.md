# OPSRECALL — Evaluation Benchmark Methodology & Anti-Leakage Specification

**Version**: 2.0 (12-Scenario Expanded Holdout Benchmark)  
**Auditor**: Evaluation Research & QA Lead  
**Specification Date**: November 5, 2026  

---

## 1. Architectural Ground-Truth Isolation

To guarantee scientific validity and eliminate data leakage, OPSRECALL strictly decouples input telemetry from evaluator answer keys across separate physical files:

```
+------------------------------------------------------------------------------------+
|                                    INPUT LAYER                                     |
|                                                                                    |
|   data/evaluation_cases.json                                                       |
|   Contains ONLY model-facing operational telemetry:                                |
|   • case_id, service_name, severity, incident_type                                 |
|   • symptoms, error_logs, metrics_snapshot, deployment_change, notes               |
|   [STRICT ZERO GROUND TRUTH]: Contains no answer keys, causes, or optimal actions   |
+-----------------------------------------+------------------------------------------+
                                          |
                                          v
+------------------------------------------------------------------------------------+
|                                 REASONING ENGINES                                  |
|                                                                                    |
|   1. Baseline (Memory OFF): Evaluates raw telemetry without memory context.        |
|   2. OPSRECALL (Memory ON): Evaluates telemetry augmented with recalled memories.  |
+-----------------------------------------+------------------------------------------+
                                          | (Generates InvestigationResult)
                                          v
+------------------------------------------------------------------------------------+
|                                 EVALUATION GRADER                                  |
|                                                                                    |
|   data/evaluation_ground_truth.json (Evaluator-Only)                               |
|   Contains verified rubrics loaded strictly by core/evaluation.py:                 |
|   • ground_truth_root_cause                                                        |
|   • ground_truth_failed_fix                                                        |
|   • optimal_first_action                                                           |
|   • acceptable_hypotheses                                                          |
|   • anti_patterns_to_avoid                                                         |
+------------------------------------------------------------------------------------+
```

Neither the LLM prompt builder (`core/llm_engine.py`) nor the investigation orchestrator (`core/investigation.py`) ever import or read `data/evaluation_ground_truth.json`.

---

## 2. Benchmark Case Taxonomy (12 Diverse Scenarios)

The benchmark consists of 12 production-grade incident scenarios categorized into three archetypes:

### Archetype A: Recurrent Operational Outages (EVAL-001 – EVAL-005)
Historical incident experiences exist in Hindsight. Memory ON should retrieve the exact historical precedent, flag the previously failed fix, and pinpoint the verified root cause.
- **EVAL-001 (`checkout-api`)**: Latency surge post-deployment DEP-8492 caused by database connection pool misconfiguration (max connections capped at 10). *Failed mitigation:* Increasing client timeouts worsened thread starvation. *Verified remedy:* Restoring pool size to 150.
- **EVAL-002 (`order-fulfillment-worker`)**: Queue backlog buildup of 38,000 orders post-deployment DEP-8510 caused by worker capacity reduction (replicas=1, concurrency=2). *Failed mitigation:* Purging dead-letter queue. *Verified remedy:* Restoring HPA minReplicas=12, concurrency=8.
- **EVAL-003 (`payment-gateway`)**: 100% 502 Bad Gateway outages caused by expired downstream internal TLS certificate. *Failed mitigation:* Bypassing ingress SSL checks in production. *Verified remedy:* Reissuing certificate via Vault CLI.
- **EVAL-004 (`catalog-service`)**: PostgreSQL CPU at 99% caused by cache stampede (synchronized 1-hour TTL without jitter). *Failed mitigation:* Flushing entire Redis cache. *Verified remedy:* Implementing single-flight mutex locks and ±15% TTL jitter.
- **EVAL-005 (`checkout-orchestrator`)**: Cascading socket exhaustion and pod crashes from external payment partner latency. *Failed mitigation:* Repeatedly restarting pods and increasing memory. *Verified remedy:* Fast-fail circuit breaker (3s) with secondary payment provider fallback.

### Archetype B: Novel Distractors & Negative Controls (EVAL-006, EVAL-012)
Unprecedented failure modes with zero historical precedent in Hindsight. The system must recognize the absence of historical matches and avoid hallucinatory false recall.
- **EVAL-006 (`cdn-edge`)**: Cloudfront 403 Forbidden errors caused by S3 bucket policy misconfiguration. Unrelated to any database or worker incidents.
- **EVAL-012 (`event-streaming-pipeline`)**: Kafka consumer group rebalance storm caused by heartbeat timeout misconfiguration during partition reassignment.

### Archetype C: Holdout Edge Cases & Stress Scenarios (EVAL-007 – EVAL-011)
Subtle operational edge cases testing discrimination under noisy telemetry:
- **EVAL-007 (`checkout-api`)**: Conflicting Telemetry (HTTP 502/504 edge timeout vs DB connection spike).
- **EVAL-008 (`auth-api`)**: Same Symptom, Different Root Cause (HTTP 500 caused by token signing key rotation rather than database starvation).
- **EVAL-009 (`inventory-worker`)**: Missing Deployment Event (gradual configuration drift / background thread exhaustion).
- **EVAL-010 (`order-fulfillment-worker`)**: Outdated Historical Fix Avoidance (scaling replicas in a saturated downstream environment).
- **EVAL-011 (`catalog-service`)**: Multi-Service Cascading Outage (upstream cart failure inducing downstream cache churn).

---

## 3. Seven Operational Evaluation Dimensions

Rather than relying on a single composite number, OPSRECALL scores investigations across 7 distinct dimensions:

1. **Top-1 Root Cause Precision**: Did the #1 ranked hypothesis match the verified ground-truth cause?
2. **Top-3 Root Cause Accuracy**: Did the true root cause appear in the top-3 candidate hypotheses?
3. **Failed Mitigation Avoidance Rate**: Were known failed fixes explicitly flagged with a `DO NOT REPEAT` warning?
4. **Relevance Retrieval Rate**: Were relevant historical postmortems retrieved for recurrent cases, and correctly omitted for novel distractors?
5. **False Historical Recall Rate (Lower=Better)**: Did the system hallucinate historical precedents for novel distractors? (Target: 0.0%).
6. **Recommendation Grounding**: Did the generated SOP cite specific parameters, commit IDs, and verified configurations?
7. **Uncertainty Calibration**: Did confidence scores reflect true empirical likelihood rather than uniform overconfidence?
