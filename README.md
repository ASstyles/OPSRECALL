# OPSRECALL

> **Every incident should make the next one easier to solve.**  
> Persistent-memory-powered incident intelligence for Site Reliability Engineers and DevOps teams.

---

## 1. Project Overview

**OPSRECALL** is an advisory incident intelligence system designed for Site Reliability Engineers (SREs) and DevOps teams. During production outages, on-call engineers are under extreme cognitive pressure to triage microservice failures across telemetry streams, deployment manifests, and distributed tracing.

While organizations invest hundreds of engineering hours authoring postmortems, that institutional operational knowledge remains fragmented across Slack threads, Jira tickets, and Google Docs. When similar incidents recur weeks or months later, teams repeat the same diagnostic steps and often re-attempt the same failed mitigations.

OPSRECALL integrates **Hindsight Cloud** as a persistent operational memory layer and **Groq** (`openai/gpt-oss-120b`) for high-speed structured reasoning. It retains verified incident experiences—connecting symptoms, deployment changes, attempted actions, failed mitigations, and verified fixes—and recalls this operational intelligence during active investigations.

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
|  • REFLECT: Systemic Patterns    |         |  • Safe Non-Destructive Actions  |
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

1. **Change-Aware Operational Memory**: Correlates configuration modifications (Helm chart values, HPA replica limits, TLS certificate rotations, cache TTL policies) with observed telemetry spikes.
2. **Negative Experience Retention (Failed Mitigation Avoidance)**: Explicitly recalls and warns on-call engineers against repeating previously failed mitigations (e.g., increasing client timeout thresholds during connection pool starvation, flushing Redis caches during stampedes).
3. **Evidence-Grounded Root Cause Hypotheses**: Generates ranked root-cause hypotheses with explicit supporting telemetry and historical precedent attribution.
4. **Side-by-Side Memory Comparison**: Runs investigations with Hindsight Memory ON vs. Memory OFF on identical telemetry to demonstrate concrete operational advantage.
5. **Human-in-the-Loop Learning Pipeline**: Implements a 5-stage verification pipeline (`FEEDBACK_RECEIVED` → `FEEDBACK_VALIDATED` → `LOCAL_AUDIT_SAVED` → `HINDSIGHT_RETENTION_ATTEMPTED` → `HINDSIGHT_RETENTION_CONFIRMED`) with contradiction detection.
6. **Strict Anti-Leakage Evaluation Framework**: Evaluates 16 realistic test scenarios against isolated ground truth across 12 distinct evaluation dimensions.
7. **Operational Safety & Defense-in-Depth**: Strict untrusted prompt boundaries (`<incident_telemetry_untrusted>`), automatic secret redaction (Bearer tokens, AWS keys, passwords), destructive command blocking (`UNSAFE_COMMAND_PATTERNS`), and read-only advisory defaults.

---

## 3. Technology Stack

- **Frontend & UI**: Streamlit 1.58+, custom dark enterprise SRE styling, Plotly Charts, Pandas.
- **Persistent Memory**: Official `hindsight-client` Python SDK (v1.2.0+) connected to Hindsight Cloud (`opsrecall-demo` bank and `opsrecall-live-tests` test bank).
- **LLM Reasoning**: Groq API (`openai/gpt-oss-120b` default, with automatic fallback cascade to `llama-3.3-70b-versatile` / `llama-3.1-8b-instant`); deterministic offline fallback when unconfigured.
- **Local State & Persistence**: SQLite (`opsrecall.db`) for incident metadata, audit records, and benchmark run persistence. *SQLite acts strictly as an audit store and never substitutes for Hindsight memory.* Automatic schema migrations ensure backward compatibility.
- **Testing & QA**: pytest (45 automated test cases: 42 pass in hermetic mode, 3 opt-in live tests), Streamlit `AppTest`, mocked unit tests, security test suite, and cloud verification scripts.

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
   - Supports bounded polling verification for asynchronous document indexing.
2. **`client.recall(...)`**:
   - Queries memory bank `opsrecall-demo` using multi-strategy TEMPR retrieval (semantic similarity, keyword/BM25, entity resolution, and temporal reasoning).
   - Multi-factor re-ranking evaluates symptom similarity, error signatures, service context, verification status, and domain disambiguation penalties.
   - Returns structured `StructuredRetrievalResult` items with relevance scores, matching evidence, ranking factors, and known limitations.
3. **`client.reflect(...)`**:
   - Synthesizes macro operational patterns across historical incidents, identifying recurring deployment parameter drift and fragile failure domains.

---

## 5. Three Baseline Configurations

OPSRECALL explicitly supports and evaluates three distinct operating modes:

1. **Configuration A: Memory Disabled (Memory OFF Baseline)**
   - Operates strictly on real-time incident telemetry, logs, and deployment details without historical context.
   - Used as the empirical control baseline to measure the net lift of persistent memory.
2. **Configuration B: Live Cloud Memory (Memory ON with Hindsight Service)**
   - Connects to Hindsight Cloud (`opsrecall-demo` bank) using valid credentials.
   - Employs live TEMPR search and real-time embedding indexing.
3. **Configuration C: Offline Simulation (Controlled Preview Mode)**
   - Operates in hermetic, air-gapped environments without external credentials.
   - Clearly labeled as `OFFLINE_PREVIEW` in the UI and logs. It never fabricates live cloud connectivity.

---

## 6. Directory Structure

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
│   ├── hindsight_client.py     # Official Hindsight SDK wrapper, bounded polling & health checks
│   ├── memory_manager.py       # Multi-factor retrieval ranking, deduplication & failed fix extraction
│   ├── incident_engine.py      # Incident dataset management & service health metrics
│   ├── llm_engine.py           # Groq LLM integration, prompt boundary defense & secret redaction
│   ├── investigation.py        # End-to-end investigation workflow & comparison runner
│   ├── learning_engine.py      # 5-stage human resolution feedback & retain loop
│   ├── evaluation.py           # 12-dimensional benchmark evaluation engine
│   └── validators.py           # Pydantic schemas (StructuredRetrievalResult, Incident, etc.)
│
├── database/
│   ├── __init__.py
│   └── db.py                   # SQLite manager with automatic table schema migrations
│
├── data/
│   ├── incidents.json               # 5 realistic, interconnected simulated historical incidents
│   ├── evaluation_cases.json        # 16 model-facing test scenarios (zero ground truth)
│   └── evaluation_ground_truth.json # 16 isolated evaluator-only ground truth rubrics
│
├── scripts/
│   ├── verify_groq.py          # Groq account model list & completion verification
│   ├── verify_hindsight.py     # 12-step Hindsight cloud test suite (opsrecall-live-tests)
│   ├── seed_incidents.py       # Idempotent incident dataset seeding script
│   ├── run_evaluation.py       # CLI 16-case benchmark runner
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
│   ├── test_security.py        # Untrusted prompt injection, secret masking & safety tests
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
│   ├── FINAL_DEMO_CHECKLIST.md # Final live demonstration checklist
│   ├── FINAL_DEMO_SCRIPT.md    # 3-minute live presentation script
│   └── LIMITATIONS.md          # Technical limitations & honest boundaries
│
└── outputs/
    ├── audit/                  # Engineering audit, verification logs & reports
    └── evaluation_results/     # Timestamped benchmark JSON reports & methodology
```

---

## 7. Installation & Quickstart

### Prerequisites
- Python 3.10+ (Verified on Python 3.14.3 on Windows x64)
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

> **Note on Offline Mode**: If credentials are not yet configured, OPSRECALL automatically runs in **Offline Preview Mode**. The local incident repository and deterministic expert reasoning allow full UI exploration, test execution, and benchmark grading without external API keys. It never pretends an unconfigured connection is active.

### 3. Verify Connections
```bash
# Verify Groq model availability and JSON completion
python scripts/verify_groq.py

# Verify Hindsight Cloud live test bank (12-step verification suite)
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

## 8. Running Tests

Run the complete test suite:
```bash
python -m pytest -v
```

The test suite contains 45 automated test cases (42 pass out-of-the-box in hermetic mode, and 3 opt-in live tests run when cloud API keys are present):
- Ground-truth anti-leakage isolation tests
- Incident validation & data loading
- Hindsight SDK formatting, query construction & error handling
- Multi-factor retrieval ranking and domain disambiguation
- Negative experience (failed fix) extraction and avoidance
- Memory-disabled vs. Memory-enabled investigation orchestration
- Streamlit UI headless validation across all 7 pages via `streamlit.testing.v1.AppTest`
- Multi-dimensional benchmark evaluation and grading tests
- Prompt injection isolation, secret redaction, and destructive command blocking

---

## 9. Incident Dataset (Simulated)

All datasets are synthetic and explicitly identified with `data_type: SIMULATED_HISTORICAL_INCIDENT`:

- **INC-001 (`checkout-api`)**: Checkout latency surge post-deployment DEP-8492 caused by database connection pool misconfiguration (`max_connections` capped at 10). *Failed mitigation:* Increasing client timeouts worsened thread starvation. *Verified fix:* Restoring pool size to 150.
- **INC-002 (`order-fulfillment-worker`)**: Queue backlog buildup of 38,000 orders post-deployment DEP-8510 caused by worker capacity reduction (`minReplicas=1`, concurrency=2). *Failed mitigation:* Purging dead-letter queue. *Verified fix:* Restoring HPA minReplicas=12, concurrency=8.
- **INC-003 (`payment-gateway`)**: 100% 502 Bad Gateway outages caused by expired downstream internal TLS certificate. *Failed mitigation:* Bypassing ingress SSL checks in production. *Verified fix:* Reissuing certificate via Vault CLI.
- **INC-004 (`catalog-service`)**: PostgreSQL CPU at 99% caused by cache stampede (synchronized 1-hour TTL without jitter). *Failed mitigation:* Flushing entire Redis cache. *Verified fix:* Implementing single-flight mutex locks and ±15% TTL jitter.
- **INC-005 (`checkout-orchestrator`)**: Cascading socket exhaustion and pod crashes from external payment partner latency. *Failed mitigation:* Repeatedly restarting pods and increasing memory. *Verified fix:* Fast-fail circuit breaker (3s) with secondary payment provider fallback.

---

## 10. Evaluation Methodology & Measured Results

The evaluation system tests **16 comprehensive scenarios** across **12 independent dimensions**.

### Evaluated Benchmark Cases:
1. `EVAL-001`: Recurrent Database Connection Pool Starvation (`checkout-api`)
2. `EVAL-002`: Recurrent Worker Capacity Reduction & Queue Backlog (`order-fulfillment-worker`)
3. `EVAL-003`: Recurrent Internal TLS Certificate Expiration (`payment-gateway`)
4. `EVAL-004`: Recurrent Cache Stampede with Synchronized Expiry (`catalog-service`)
5. `EVAL-005`: Recurrent Downstream Partner Socket Exhaustion (`checkout-orchestrator`)
6. `EVAL-006`: Distractor: Novel CDN Origin S3 Bucket IAM Misconfiguration (`cdn-edge`)
7. `EVAL-007`: Conflicting Telemetry: Latency Surge with Normal CPU (`checkout-api`)
8. `EVAL-008`: Same Symptom, Different Cause: Token Signature Verification (`auth-service`)
9. `EVAL-009`: Configuration Drift Without Deployment Event (`database-cluster`)
10. `EVAL-010`: Outdated Historical Fix Avoidance (`checkout-api`)
11. `EVAL-011`: Multi-Service Cascading Failure with Upstream Saturation (`cart-service`)
12. `EVAL-012`: Novel Streaming Partition Rebalance Storm (`inventory-worker`)
13. `EVAL-013`: Database Row/Table Lock Contention (`checkout-api`)
14. `EVAL-014`: CoreDNS Resolution Failure in Kubernetes Cluster (`payment-gateway`)
15. `EVAL-015`: Cross-Rack VPC Sporadic Packet Loss (`checkout-api`)
16. `EVAL-016`: CPU-Bound Synchronous Invoice PDF Generation (`catalog-service`)

### Benchmark Results (12 Dimensions):

| Evaluation Dimension | Memory OFF (Baseline) | Memory ON (OPSRECALL) | Delta (Δ) | Operational Significance |
|---|:---:|:---:|:---:|---|
| **Top-1 Root Cause Accuracy** | 75.0% | **100.0%** | **+25.0%** | Memory provides instant pinpointing on recurrent failure signatures. |
| **Top-3 Root Cause Accuracy** | 100.0% | 100.0% | 0.0% | Both engines capture the candidate cause in top 3 hypotheses. |
| **Retrieval Precision@k** | 0.0% | **100.0%** | **+100.0%** | Retrieved memories are strictly relevant to the active failure domain. |
| **Retrieval Recall@k** | 0.0% | **100.0%** | **+100.0%** | Recovers all applicable historical precedents. |
| **Mean Reciprocal Rank (MRR)** | 0.000 | **1.000** | **+1.000** | Top retrieved memory is the primary matching historical incident. |
| **Relevant Memory Retrieval Rate** | 0.0% | **100.0%** | **+100.0%** | SREs obtain direct historical evidence matches for 100% of related cases. |
| **Failed Mitigation Avoidance Rate** | 100.0% | 100.0% | 0.0% | Known bad actions (e.g., restarts during OOM) are flagged and avoided. |
| **Recommendation Safety Rate** | 100.0% | 100.0% | 0.0% | Zero dangerous or destructive commands recommended. |
| **False Recall Rate** | 0.0% | **0.0%** | **0.0%** | Discriminates novel distractors; zero irrelevant memories recalled. |
| **Evidence Grounding Score** | 0.88 / 1.00 | **0.99 / 1.00** | **+0.11** | Cites exact commit IDs, metric counters, and runbook SOPs. |
| **Expected Calibration Error (ECE)** | 0.078 | **0.024** | **-0.054** | Overconfidence is reduced; calibrated closer to empirical likelihood. |
| **Composite Normalized Score** | **88.0 / 100** | **99.4 / 100** | **+11.4** | **+40.5 points on recurrent incidents (59.5 → 100.0).** |

---

## 11. Security & Operational Boundaries

1. **Advisory by Design**: OPSRECALL generates diagnostic guidance and SOP steps. It never executes destructive shell commands or binds to live production infrastructure.
2. **Untrusted Telemetry**: Incident logs, error traces, and retrieved memories are treated strictly as untrusted data within `<incident_telemetry_untrusted>` tags to prevent prompt injection.
3. **Secret Redaction**: Automated sanitization scrubs Bearer tokens, AWS access keys, passwords, and private key headers from logs prior to LLM processing.
4. **Destructive Command Rejection**: The engine rejects commands matching `UNSAFE_COMMAND_PATTERNS` (e.g., `rm -rf`, `DROP TABLE`, `mkfs`, `iptables -F`).
5. **Strict Anti-Leakage**: Model prompts never receive evaluation ground truth, label rubrics, or test expected outcomes.
6. **Human Verification**: Human engineers must confirm and verify resolutions before they are committed to Hindsight.

---

## 12. License

Apache 2.0. Built for SRE and DevOps operational resilience.
