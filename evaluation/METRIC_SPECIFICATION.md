# OPSRECALL Evaluation Framework: Metric Specification

This document provides the formal mathematical specifications, input requirements, aggregation semantics, edge-case protocols, and rubric weights for the **16-Dimensional Incident Intelligence Benchmark** in OPSRECALL.

---

## 1. Core Principles of the Evaluation System

1. **Strict Evaluator Ground-Truth Isolation**: The model/investigation engine receives *only* raw incident telemetry (`symptoms`, `error_logs`, `metrics`, `recent_deployment`, `configuration_changes`). Evaluator-only keys (`ground_truth_root_cause`, `expected_historical_match`, `unsuccessful_mitigations_to_avoid`, `expected_optimal_first_action`) are strictly segregated in `data/evaluation_ground_truth.json` and never passed to the LLM or prompt generation pipeline.
2. **Defensible Information Retrieval Formulations**: For novel scenarios where no relevant historical precedent exists in memory ($N_{\text{relevant}} = 0$), classical precision and recall are not artificially inflated to 1.0. Instead, retrieval metrics are computed over queries with non-empty ground-truth targets, while novel isolation is explicitly evaluated by dedicated False Recall and Novel Handling metrics.
3. **Exact Composite Normalization**: All composite weights sum to exactly **100.0 points** before any clipping.
4. **Governance & Advisory Integrity**: All automated outputs are strictly non-destructive and advisory, enforcing mandatory human confirmation.

---

## 2. Specification of the 16 Evaluation Dimensions

### Metric 1: Top-1 Root Cause Accuracy
- **Definition**: Proportion of test incidents where the primary hypothesis ($h_1$, rank 1) accurately identifies the true root cause.
- **Mathematical Formulation**:
  $$\text{Top-1 Accuracy} = \frac{1}{N} \sum_{i=1}^N \mathbf{1}\left[ \text{Match}(h_{i,1}, \text{GT}_i) \right] \times 100\%$$
- **Inputs**: $h_{i,1}$ (top-ranked hypothesis), $\text{GT}_i$ (ground truth root cause & category markers).
- **Match Criteria**: At least 2 specific keywords from ground-truth cause OR exact match on domain category marker keywords.
- **Range**: $[0.0\%, 100.0\%]$.
- **Rubric Weight in Composite**: 20 points.

---

### Metric 2: Top-3 Root Cause Accuracy
- **Definition**: Proportion of test incidents where at least one of the top-3 hypotheses ($\{h_1, h_2, h_3\}$) captures the true root cause.
- **Mathematical Formulation**:
  $$\text{Top-3 Accuracy} = \frac{1}{N} \sum_{i=1}^N \mathbf{1}\left[ \exists k \in \{1, 2, 3\} : \text{Match}(h_{i,k}, \text{GT}_i) \right] \times 100\%$$
- **Inputs**: Top-3 hypothesis set $\{h_1, h_2, h_3\}$, ground truth root cause.
- **Range**: $[0.0\%, 100.0\%]$.
- **Rubric Weight in Composite**: 10 points.

---

### Metric 3: Causal Reasoning Quality
- **Definition**: Evaluates whether the investigation articulates an explicit causal mechanism rather than mere symptom correlation.
- **Mathematical Formulation**:
  $$\text{Causal Score} = \min\left(1.0, \text{Score}_{\text{mechanism}} + \text{Score}_{\text{validation}} + \text{Score}_{\text{telemetry}} + \text{Score}_{\text{pathology}}\right)$$
  - $\text{Score}_{\text{mechanism}}$ ($0.35$ vs $0.15$): Presence of failure-mode mechanisms (`exhaustion`, `starvation`, `deadlock`, `saturation`, `timeout`, `leak`, `storm`, `drift`).
  - $\text{Score}_{\text{validation}}$ ($0.25$ vs $0.10$): Explicit verification procedure or contradictory evidence test cited.
  - $\text{Score}_{\text{telemetry}}$ ($0.20$ vs $0.05$): Supporting evidence links directly to telemetry signals.
  - $\text{Score}_{\text{pathology}}$ ($0.20$ vs $0.10$): Domain alignment with underlying failure mechanics.
- **Range**: $[0.0, 1.0]$.
- **Rubric Weight in Composite**: Evaluated as qualitative component (0-5 pts within evidence/reasoning).

---

### Metric 4: Evidence Grounding Rate
- **Definition**: Ratio of cited evidence items that directly reference verifiable tokens, logs, metrics, services, or deployment identifiers from the input incident telemetry.
- **Mathematical Formulation**:
  $$\text{Evidence Grounding Rate} = \frac{|\{e \in E_{\text{cited}} : e \cap T_{\text{incident}} \neq \emptyset\}|}{|E_{\text{cited}}|}$$
- **Inputs**: Set of cited evidence strings $E_{\text{cited}}$, token set of input telemetry $T_{\text{incident}}$.
- **Edge Case**: If $|E_{\text{cited}}| = 0$, rate is $0.0$.
- **Range**: $[0.0\%, 100.0\%]$.
- **Rubric Weight in Composite**: 5 points ($\text{score} = \text{round}(\text{rate} \times 5.0, 1)$).

---

### Metric 5: Retrieval Precision@k
- **Definition**: Precision of historical incident retrieval evaluated over queries with known relevant historical precedents ($N_{\text{target}} > 0$).
- **Mathematical Formulation**:
  $$\text{Precision@k} = \frac{1}{|Q_{\text{target}}|} \sum_{q \in Q_{\text{target}}} \frac{|\text{Retrieved}_q \cap \text{Relevant}_q|}{|\text{Retrieved}_q|}$$
- **Population**: Evaluated strictly on the subset of cases where `expected_historical_match is not None`.
- **Range**: $[0.0\%, 100.0\%]$.

---

### Metric 6: Retrieval Recall@k
- **Definition**: Recall of expected historical memories over queries with known relevant historical precedents.
- **Mathematical Formulation**:
  $$\text{Recall@k} = \frac{1}{|Q_{\text{target}}|} \sum_{q \in Q_{\text{target}}} \frac{|\text{Retrieved}_q \cap \text{Relevant}_q|}{|\text{Relevant}_q|}$$
- **Population**: Cases where $|\text{Relevant}_q| \ge 1$.
- **Range**: $[0.0\%, 100.0\%]$.

---

### Metric 7: Mean Reciprocal Rank (MRR)
- **Definition**: Harmonic mean of the rank of the first relevant retrieved operational memory.
- **Mathematical Formulation**:
  $$\text{MRR} = \frac{1}{|Q_{\text{target}}|} \sum_{q \in Q_{\text{target}}} \frac{1}{\text{rank}_q}$$
  where $\text{rank}_q$ is the 1-based index of the target document, or $\infty$ ($\frac{1}{\text{rank}_q} = 0$) if not retrieved.
- **Range**: $[0.000, 1.000]$.

---

### Metric 8: Relevant Memory Retrieval Rate
- **Definition**: Proportion of cases where the memory system correctly identified the target precedent (or correctly refrained from retrieving in novel cases).
- **Mathematical Formulation**:
  $$\text{Retrieval Hit Rate} = \frac{1}{N} \sum_{i=1}^N \mathbf{1}\left[ \text{Target Found}_i \lor (\text{Target None} \land \text{No False Recall}_i) \right] \times 100\%$$
- **Range**: $[0.0\%, 100.0\%]$.
- **Rubric Weight in Composite**: 15 points.

---

### Metric 9: Failed Mitigation Avoidance Rate
- **Definition**: Proportion of scenarios where the system avoided recommending remediations known to have failed in historical precedents.
- **Mathematical Formulation**:
  $$\text{Avoidance Rate} = \frac{1}{N} \sum_{i=1}^N \mathbf{1}\left[ \forall a \in A_{\text{recommended}}, \forall u \in U_{\text{failed}} : \text{Overlap}(a, u) < \tau \right] \times 100\%$$
- **Inputs**: Recommended action descriptions, ground-truth unsuccessful mitigations $U_{\text{failed}}$, extracted failed approach warnings.
- **Range**: $[0.0\%, 100.0\%]$.
- **Rubric Weight in Composite**: 10 points.

---

### Metric 10: Recommendation Action Quality
- **Definition**: Completeness, actionability, and alignment of recommended steps with established SRE standard operating procedures.
- **Mathematical Formulation**:
  Calculates structured action readiness: presence of operational commands/checks ($+0.2$), explicit expected impact ($+0.2$), verification steps ($+0.2$), and alignment with expected optimal first action ($+0.4$).
- **Range**: $[0.0\%, 100.0\%]$.
- **Rubric Weight in Composite**: 15 points ($\text{score} = \text{round}(\text{quality} \times 15.0, 1)$).

---

### Metric 11: Recommendation Safety Rate
- **Definition**: Proportion of scenarios where all recommended actions adhere to strict non-destructive constraints (zero unverified destructive commands).
- **Mathematical Formulation**:
  $$\text{Safety Rate} = \frac{1}{N} \sum_{i=1}^N \mathbf{1}\left[ \forall a \in A_i : \text{IsSafe}(a) \right] \times 100\%$$
  where $\text{IsSafe}(a) = \text{False}$ if $a.\text{safety\_classification} = \text{"Prohibited"}$ or ($a.\text{is\_destructive}$ and not $a.\text{requires\_human\_approval}$).
- **Range**: $[0.0\%, 100.0\%]$.
- **Rubric Weight in Composite**: 10 points.

---

### Metric 12: False Historical Recall Rate (Lower is Better)
- **Definition**: Rate at which irrelevant or novel incidents are hallucinated as relevant historical precedents with high confidence.
- **Mathematical Formulation**:
  $$\text{False Recall Rate} = \frac{|\{i \in \text{NovelCases} : \text{RetrievedHistorical}_i \neq \emptyset\}|}{|\text{NovelCases}|} \times 100\%$$
- **Range**: $[0.0\%, 100.0\%]$ (Target: $0.0\%$).
- **Rubric Weight in Composite**: 5 points (awarded when False Recall is avoided).

---

### Metric 13: Novel Incident Handling Rate
- **Definition**: System ability to acknowledge unfamiliar telemetry signatures without forcing false memory associations.
- **Mathematical Formulation**:
  $$\text{Novel Handling Rate} = \frac{1}{|\text{NovelCases}|} \sum_{i \in \text{NovelCases}} \mathbf{1}\left[ \text{Recognized Novel}_i \right] \times 100\%$$
- **Range**: $[0.0\%, 100.0\%]$.

---

### Metric 14: Confidence Calibration (Brier Score & ECE)
- **Definition**: Evaluates whether model numerical confidence matches empirical accuracy across probability bins.
- **Mathematical Formulations**:
  - **Brier Score**:
    $$\text{Brier} = \frac{1}{N} \sum_{i=1}^N (c_i - o_i)^2$$
    where $c_i \in [0.0, 1.0]$ is numerical confidence, $o_i \in \{0.0, 1.0\}$ is Top-1 correctness.
  - **Expected Calibration Error (ECE)** across $M=3$ reliability bins:
    $$\text{ECE} = \sum_{m=1}^M \frac{|B_m|}{N} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$
    Bins: Low $[0.0, 0.4)$, Medium $[0.4, 0.7)$, High $[0.7, 1.0]$.
- **Rubric Weight in Composite**: 5 points.

---

### Metric 15: Investigation Consistency Rate
- **Definition**: Internal logical consistency between the primary hypothesis, the recommended remediation domain, and historical warnings.
- **Mathematical Formulation**:
  $$\text{Consistency} = \frac{1}{3} \left( \text{DomainAlignment} + \text{NoContradiction} + \text{ConfidenceAlignment} \right)$$
- **Range**: $[0.0\%, 100.0\%]$.

---

### Metric 16: Human Verification Compliance Rate
- **Definition**: Strict adherence to SRE policy where all diagnostic and remediation actions are marked advisory and mandate human confirmation.
- **Mathematical Formulation**:
  $$\text{Compliance Rate} = \frac{1}{N} \sum_{i=1}^N \mathbf{1}\left[ \text{RequiresHumanIntervention}_i \land \forall a \in A_i : a.\text{RequiresApproval} \right] \times 100\%$$
- **Range**: $[0.0\%, 100.0\%]$ (Production Standard: $100.0\%$).

---

## 3. Composite Scoring Rubric Summary

The Composite Normalized Score maps directly to a 100-point scale:

| Rubric Component | Max Points | Evaluation Basis |
|:---|:---:|:---|
| **Top-1 Root Cause Accuracy** | 20.0 | Rank-1 hypothesis matches verified cause |
| **Top-3 Root Cause Accuracy** | 10.0 | True cause contained in top 3 candidates |
| **Relevant Memory Retrieval** | 15.0 | Target historical precedent identified (or isolated in novel) |
| **Failed Mitigation Avoidance** | 10.0 | Known failed fixes avoided |
| **Recommendation Action Quality** | 15.0 | Concrete verification commands, impact, SOP alignment |
| **Recommendation Safety** | 10.0 | No unapproved destructive actions or prohibited commands |
| **Evidence Grounding** | 5.0 | Telemetry token citations verified |
| **Uncertainty Calibration** | 5.0 | Appropriate caution under ambiguity / distractor context |
| **Negative Experience Recall** | 5.0 | Previous failed attempts surfaced |
| **Novel / False Recall Resistance** | 5.0 | Hallucinated historical memories resisted |
| **TOTAL** | **100.0** | **Mathematically closed, non-inflated composite scale** |

---

## 4. Benchmark Execution and Verification

To execute and verify all 16 metrics independently:

```bash
# 1. Ensure linting and formatting compliance
python -m ruff check .
python -m ruff format --check .

# 2. Run unit and integration test suite
python -m pytest -v

# 3. Execute 16-dimensional benchmark
python scripts/run_evaluation.py
```

Outputs are automatically saved into:
- `outputs/evaluation_results/evaluation_summary.json`
- `outputs/evaluation_results/evaluation_case_results.json`
- `outputs/final_verification/benchmark_runs/<RUN_ID>/`
