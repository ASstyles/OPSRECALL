# OPSRECALL

> **Every incident should make the next one easier to solve.**  
> Persistent-memory-powered incident intelligence for Site Reliability Engineers and DevOps teams.

---

## 1. Project Overview

**OPSRECALL** is an advisory incident investigation agent designed for Site Reliability Engineers (SREs) and DevOps teams. During production outages, on-call engineers are under extreme pressure to diagnose complex failures across microservices, telemetry streams, and deployment pipelines. 

While organizations write detailed incident postmortems, that knowledge remains fragmented across Jira tickets, Google Docs, Slack threads, and Confluence pages. When similar incidents recur weeks or months later, teams repeat the same time-consuming diagnostic steps and often attempt the same failed mitigations.

OPSRECALL integrates **Hindsight Cloud** as a persistent operational memory layer and **Groq** (`openai/gpt-oss-120b`) for high-speed structured reasoning. It retains verified incident experiences—connecting symptoms, deployment changes, attempted actions, failed mitigations, and verified fixes—and recalls this operational intelligence during new investigations.

```
+-------------------------------------------------------------------------------+
|                             Streamlit SRE Console                             |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
                    +---------------------------------------+
                    |     Incident Investigation Engine     |
                    +-------------------+-------------------+
                                        |
                 +----------------------+----------------------+
                 |                                             |
                 v                                             v
+----------------------------------+         +----------------------------------+
|     Hindsight Memory Bank        |         |             Groq LLM             |
|   opsrecall-demo / live-tests    |         |        openai/gpt-oss-120b       |
|  • RETAIN: Verified Postmortems  |         |  • Structured JSON Hypotheses    |
|  • RECALL: TEMPR Search Engine   |         |  • Actionable SOP Diagnostics    |
|  • REFLECT: Systemic Patterns    |         |  • Safe Non-Destructive Remediation |
+----------------+-----------------+         +-----------------+----------------+
                 |                                             |
                 +----------------------+----------------------+
                                        |
                                        v
                    +---------------------------------------+
                    |       Evidence & Decision Layer       |
                    |  • Side-by-Side Memory Comparison     |
                    |  • Previous Failed Mitigations Alert  |
                    |  • SQLite Local Audit Logging         |
                    +-------------------+-------------------+
                                        |
                                        v
                    +---------------------------------------+
                    |      Human Engineer Verification      |
                    |  • Confirm Root Cause & Resolution    |
                    |  • Retain Experience into Hindsight   |
                    +---------------------------------------+
```

---

## 2. Key Capabilities

1. **Change-Aware Operational Memory**: Correlates configuration changes (Helm chart updates, HPA replica modifications, TLS expiry, cache TTL changes) with observed telemetry spikes.
2. **Negative Experience Retention (Failed Fix Avoidance)**: Explicitly recalls and warns on-call engineers against repeating previously failed mitigations (e.g., increasing timeout thresholds during connection pool starvation, flushing Redis during a cache stampede).
3. **Evidence-Grounded Root Cause Hypotheses**: Generates top-3 root-cause hypotheses with explicit supporting telemetry and historical precedent attribution.
4. **Side-by-Side Memory Comparison**: Runs investigations with Hindsight Memory ON vs. Memory OFF on identical telemetry to demonstrate concrete operational advantage.
5. **Human-in-the-Loop Learning**: Engineers confirm root causes and successful resolutions before retaining newly acquired experience into Hindsight.
6. **Strict Anti-Leakage Evaluation Framework**: Evaluates 12 realistic test scenarios against isolated ground truth across 7 distinct evaluation dimensions.

---

## 3. Technology Stack

- **Frontend & UI**: Streamlit 1.58+, custom dark enterprise CSS, Plotly Charts, Pandas.
- **Persistent Memory**: Official `hindsight-client` Python SDK (v1.2.0+) connected to Hindsight Cloud (`opsrecall-demo` bank and `opsrecall-live-tests` test bank).
- **LLM Reasoning**: Groq API (`openai/gpt-oss-120b` default, with automatic fallback cascade to `llama-3.3-70b-versatile` / `llama-3.1-8b-instant`); deterministic offline fallback when unconfigured.
- **Local State & Persistence**: SQLite (`opsrecall.db`) for incident metadata, audit records, and benchmark run persistence. *SQLite acts strictly as an audit store and never substitutes for Hindsight memory.*
- **Testing & QA**: pytest (35 test cases), Streamlit `AppTest`, mocked unit tests, and opt-in live cloud integration tests.

---

## 4. Hindsight Integration

OPSRECALL integrates directly with the official Hindsight Python SDK (`hindsight-client` 1.2.0):

```python
from hindsight_client import Hindsight

client = Hindsight(
    base_url="https://api.hindsight.vectorize.io",
    api_key="your_hindsight_api_key",
    timeout=30.0,
    user_agent="OPSRECALL-Incident-Agent/1.0"
)
```

### The Three Operational Pillars:

1. **`client.retain(...)`**:
   - Stores structured incident documents with stable `document_id=incident.incident_id` to guarantee idempotent seeding.
   - Attaches service tags (`tags=[incident.affected_service, incident.severity.lower(), "incident-experience", "verified-resolution"]`).
   - Retains context, error logs, and both successful and failed mitigations.
2. **`client.recall(...)`**:
   - Queries memory bank `opsrecall-demo` using multi-strategy TEMPR retrieval (semantic similarity, keyword/BM25, entity resolution, and temporal reasoning).
   - Returns structured `RecallResult` items with relevance scores, source incident IDs, and provenance metadata.
3. **`client.reflect(...)`**:
   - Synthesizes macro operational patterns across historical incidents, identifying recurring deployment parameter drift and fragile failure domains.

---

## 5. Directory Structure

```
OPSRECALL/
├── app.py                      # Main Streamlit SRE Dashboard
├── config.py                   # Centralized configuration & environment loader
├── requirements.txt            # Python dependencies
├── .env.example                # Example environment variable template
├── .gitignore                  # Git ignore rules
├── README.md                   # Complete documentation
│
├── core/
│   ├── __init__.py
│   ├── hindsight_client.py     # Official Hindsight SDK wrapper & health checks
│   ├── memory_manager.py       # Memory formatting, query formulation & failed fix extraction
│   ├── incident_engine.py      # Incident dataset management & service health metrics
│   ├── llm_engine.py           # Groq LLM integration & structured reasoning (openai/gpt-oss-120b)
│   ├── investigation.py        # End-to-end investigation workflow & comparison runner
│   ├── learning_engine.py      # Human resolution feedback & retain loop
│   ├── evaluation.py           # Multi-dimensional benchmark evaluation suite
│   └── validators.py           # Pydantic schemas (Incident, InvestigationResult, etc.)
│
├── database/
│   ├── __init__.py
│   └── db.py                   # SQLite manager for local audit logging
│
├── data/
│   ├── incidents.json               # 5 realistic, interconnected simulated historical incidents
│   ├── evaluation_cases.json        # 12 model-facing test scenarios (zero ground truth)
│   └── evaluation_ground_truth.json # 12 isolated evaluator-only ground truth rubrics
│
├── scripts/
│   ├── verify_groq.py          # Groq account model list & completion verification
│   ├── verify_hindsight.py     # 10-step Hindsight cloud test suite (opsrecall-live-tests)
│   ├── seed_incidents.py       # Idempotent incident dataset seeding script
│   ├── run_evaluation.py       # CLI 12-case benchmark runner
│   └── generate_architecture_diagram.py # Architecture visual generator
│
├── tests/
│   ├── test_validators.py      # Data validation & schema tests
│   ├── test_incidents.py       # Incident repository & SQLite tests
│   ├── test_memory.py          # Hindsight client mock, formatting & recall tests
│   ├── test_investigation.py   # Investigation engine & side-by-side comparison tests
│   ├── test_learning.py        # Resolution feedback & retain tests
│   ├── test_evaluation.py      # Benchmark runner & isolated grading tests
│   ├── test_ui.py              # Streamlit AppTest headless UI tests
│   └── test_live_integration.py# Opt-in live cloud integration tests
│
├── assets/
│   └── architecture.png        # System architecture diagram
│
├── submission/
│   ├── ARTICLE.md              # Technical deep-dive article (~1,400 words)
│   ├── LINKEDIN_POST.md        # Technical announcement post (<800 chars)
│   ├── VIDEO_SCRIPT.md         # Video demonstration script (2-5 min)
│   ├── DEMO_CHECKLIST.md       # Live repeatable walkthrough checklist
│   └── LIMITATIONS.md          # Technical limitations & honest boundaries
│
└── outputs/
    ├── audit/                  # Engineering audit, migration, and verification logs
    └── evaluation_results/     # Timestamped benchmark JSON reports & methodology
```

---

## 6. Installation & Quickstart

### Prerequisites
- Python 3.10+ (Verified on Python 3.14 on Windows)
- pip / virtualenv

### 1. Clone & Install Dependencies
```bash
git clone <repository_url>
cd OPSRECALL
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` with your API keys:
```env
HINDSIGHT_API_KEY=your_hindsight_api_key_here
HINDSIGHT_BANK_ID=opsrecall-demo
HINDSIGHT_TEST_BANK_ID=opsrecall-live-tests
HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io

GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
SQLITE_DB_PATH=opsrecall.db
```

> **Note on Offline Mode**: If credentials are not yet configured, OPSRECALL automatically runs in **Offline Preview Mode**. The local incident repository and deterministic expert reasoning allow full UI exploration and test execution without external API keys. It never pretends an unconfigured connection is active.

### 3. Verify Connections
```bash
# Verify Groq model availability and JSON completion
python scripts/verify_groq.py

# Verify Hindsight Cloud live test bank
python scripts/verify_hindsight.py
```

### 4. Seed Historical Incident Experiences
```bash
python scripts/seed_incidents.py
```

### 5. Run Benchmark Evaluation
```bash
python scripts/run_evaluation.py
```

### 6. Launch Dashboard
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## 7. Running Tests

Run the complete test suite:
```bash
python -m pytest -v
```

The test suite runs 35 automated tests (32 pass out-of-the-box in hermetic mode, and 3 opt-in live tests run when cloud API keys are present):
- Ground-truth anti-leakage isolation tests
- Incident validation & data loading
- Hindsight SDK formatting, query construction & error handling
- Negative experience (failed fix) extraction
- Memory-disabled vs. Memory-enabled investigation orchestration
- Streamlit UI headless validation across all 7 pages via `streamlit.testing.v1.AppTest`
- Multi-dimensional benchmark evaluation and grading tests

---

## 8. Incident Dataset (Simulated)

All datasets are synthetic and explicitly identified with `data_type: SIMULATED_HISTORICAL_INCIDENT`:

- **INC-001 (`checkout-api`)**: Checkout latency surge post-deployment DEP-8492 caused by database connection pool misconfiguration (max connections capped at 10). *Failed mitigation:* Increasing client timeouts worsened thread starvation. *Verified fix:* Restoring pool size to 150.
- **INC-002 (`order-fulfillment-worker`)**: Queue backlog buildup of 38,000 orders post-deployment DEP-8510 caused by worker capacity reduction (replicas=1, concurrency=2). *Failed mitigation:* Purging dead-letter queue. *Verified fix:* Restoring HPA minReplicas=12, concurrency=8.
- **INC-003 (`payment-gateway`)**: 100% 502 Bad Gateway outages caused by expired downstream internal TLS certificate. *Failed mitigation:* Bypassing ingress SSL checks in production. *Verified fix:* Reissuing certificate via Vault CLI.
- **INC-004 (`catalog-service`)**: PostgreSQL CPU at 99% caused by cache stampede (synchronized 1-hour TTL without jitter). *Failed mitigation:* Flushing entire Redis cache. *Verified fix:* Implementing single-flight mutex locks and ±15% TTL jitter.
- **INC-005 (`checkout-orchestrator`)**: Cascading socket exhaustion and pod crashes from external payment partner latency. *Failed mitigation:* Repeatedly restarting pods and increasing memory. *Verified fix:* Fast-fail circuit breaker (3s) with secondary payment provider fallback.

---

## 9. Evaluation Methodology & Results

The benchmark evaluates **12 scenarios** (5 recurrent outages, 1 distractor, and 6 holdout edge cases including conflicting telemetry, configuration drift, and cascading failures) across **7 distinct dimensions**:

| Metric Dimension | Memory OFF (Baseline) | Memory ON (OPSRECALL) | Delta (\u0394) | Interpretation |
|---|:---:|:---:|:---:|---|
| **Top-1 Root Cause Accuracy** | 75.0% | **91.7%** | **+16.7%** | Memory provides instant pinpointing on recurrent failure signatures. |
| **Top-3 Root Cause Accuracy** | 100.0% | 100.0% | 0.0% | Both engines capture the candidate cause in top 3 hypotheses. |
| **Failed Mitigation Avoidance Rate** | 100.0% | 100.0% | 0.0% | Known bad actions (e.g., restarts during OOM) are flagged and avoided. |
| **Optimal First Action Precision** | 83.3% | **100.0%** | **+16.7%** | SREs immediately execute the verified remedy on the first attempt. |
| **Relevance Retrieval Rate** | 58.3% | **100.0%** | **+41.7%** | SREs obtain direct historical evidence matches for 100% of related cases. |
| **Evidence Grounding Score** | 0.88 / 1.00 | **0.99 / 1.00** | **+0.11** | Recommendations cite past commit IDs, runbooks, and telemetry. |
| **Mean Calibration Error** | 0.082 | **0.038** | **-0.044** | Overconfidence is reduced; calibrated closer to empirical likelihood. |
| **Macro Composite Score** | **88.3 / 100** | **98.8 / 100** | **+10.5** | **+25.0 points on recurrent incidents (75.0 -> 100.0).** |

### Scenario Breakdown

| Case ID | Service | Type / Archetype | Score (Mem OFF) | Score (Mem ON) | Delta |
|:---|:---|:---|:---:|:---:|:---:|
| **EVAL-001** | `checkout-api` | Recurrent Pool Exhaustion | 75.0 | **100.0** | **+25.0** |
| **EVAL-002** | `order-fulfillment-worker` | Recurrent Worker Throttling | 75.0 | **100.0** | **+25.0** |
| **EVAL-003** | `payment-gateway` | Recurrent TLS Expiry | 75.0 | **100.0** | **+25.0** |
| **EVAL-004** | `catalog-service` | Recurrent Cache Stampede | 75.0 | **100.0** | **+25.0** |
| **EVAL-005** | `checkout-orchestrator` | Recurrent Socket Exhaustion | 75.0 | **100.0** | **+25.0** |
| **EVAL-006** | `cdn-edge` | Distractor (Novel Edge Timeout) | 100.0 | **100.0** | +0.0 |
| **EVAL-007** | `checkout-api` | Conflicting Telemetry | 95.0 | **95.0** | +0.0 |
| **EVAL-008** | `auth-service` | Same Symptom, Different Cause | 95.0 | **95.0** | +0.0 |
| **EVAL-009** | `database-cluster` | Missing Deploy / Config Drift | 90.0 | **95.0** | **+5.0** |
| **EVAL-010** | `checkout-api` | Outdated Historical Fix Avoidance | 95.0 | **100.0** | **+5.0** |
| **EVAL-011** | `cart-service` | Multi-Service Cascade | 95.0 | **95.0** | +0.0 |
| **EVAL-012** | `inventory-worker` | Novel Streaming Rebalance | 95.0 | **95.0** | +0.0 |

---

## 10. Security & Safety Boundaries

- **Advisory Only**: OPSRECALL generates diagnostic guidance and SOP steps. It never executes destructive shell commands or binds to live production infrastructure.
- **Untrusted Telemetry**: Incident logs, error traces, and retrieved memories are treated strictly as untrusted data to analyze, not instructions to execute.
- **Strict Anti-Leakage**: Model prompts never receive evaluation ground truth, label rubrics, or test expected outcomes.
- **Human Verification**: Human engineers must confirm and verify resolutions before they are committed to Hindsight.
- **Credential Hygiene**: API keys are loaded via environment variables and never exposed in client logs or git history.

---

## 11. License

Apache 2.0. Built for SRE and DevOps operational resilience.
