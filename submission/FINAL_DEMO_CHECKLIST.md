# OPSRECALL — Final Live Demonstration Checklist

Use this repeatable checklist to verify, demonstrate, and judge OPSRECALL from the terminal to the Streamlit web dashboard.

---

## 1. Pre-Flight Terminal Verification (1 Minute)

- [ ] **Verify Python Environment**:
  ```bash
  python --version
  ```
  *(Verified on Python 3.10+ / Python 3.14 on Windows).*

- [ ] **Run Automated Test Suite (35 Tests)**:
  ```bash
  python -m pytest -q
  ```
  *Expected Output: `32 passed, 3 skipped` (0 failures).*

- [ ] **Run UI Headless Navigation Tests (7 Pages)**:
  ```bash
  python -m pytest tests/test_ui.py -v
  ```
  *Expected Output: `7 passed`.*

- [ ] **Verify Configuration Health**:
  ```bash
  python scripts/verify_groq.py
  python scripts/verify_hindsight.py
  ```
  *Expected Output: Confirms `.env` detection, masked credentials, bank ID `opsrecall-demo`, and model `openai/gpt-oss-120b`.*

---

## 2. Launch Dashboard

- [ ] **Start Streamlit Server**:
  ```bash
  streamlit run app.py
  ```
  *Access URL: `http://localhost:8501`*

---

## 3. Live Demonstration Walkthrough (3 Minutes)

### Step 1: Operational Command Center
- [ ] Inspect the 5 top KPI cards:
  - `System Mode`: Displays `OFFLINE PREVIEW` (or `LIVE CLOUD` when keys configured).
  - `Memory Bank`: Displays `opsrecall-demo` without text truncation.
  - `Active Incidents`: `5 Loaded`.
  - `SEV-1 Critical`: `3 Events`.
  - `Benchmark Runs`: `12 Records`.
- [ ] Review Monitored Service Health table and Operational Incidents cards.

### Step 2: Live AI Investigation Comparison (Core Showstopper)
- [ ] Navigate to **AI Investigation & Comparison** in the sidebar.
- [ ] Select incident `INC-001 — Checkout API Latency Spike Post-Deployment`.
- [ ] Click **⚡ Run Side-by-Side Comparison**.
- [ ] **Verify Left Column (Memory Disabled)**:
  - Shows generic hypothesis (slow query / pod underprovisioning).
  - Highlights red alert: `⚠️ CRITICAL BLIND SPOT: Zero historical failed mitigations recalled`.
  - Recommends increasing client timeouts or scaling replicas (the dangerous action!).
- [ ] **Verify Right Column (Hindsight Augmented)**:
  - Cites historical precedent `INC-001`.
  - Shows high-visibility warning: `🚫 DO NOT REPEAT FAILED MITIGATION: Increased checkout-api HTTP client timeout from 5s to 15s`.
  - Shows verified remedy: `✅ VERIFIED REMEDY (INC-001): Restore max_db_connections to 150 in Helm values and rolling restart pods`.
- [ ] Inspect the bottom Delta Comparison scorecard.

### Step 3: Negative Control & Distractor Rejection
- [ ] In the incident selector, choose an unrelated scenario: `INC-003` (TLS Expiration) or custom novel scenario.
- [ ] Verify that Hindsight does not hallucinate false connection-pool memories from `INC-001`.

### Step 4: Memory Explorer
- [ ] Navigate to **Memory Explorer**.
- [ ] Query: `checkout-api 504 gateway timeout database pool`.
- [ ] Click **Search Memories**.
- [ ] Verify structured memory cards return with similarity match scores (`Match: 0.98`) and formatted postmortem sections.

### Step 5: Incident Learning Loop
- [ ] Navigate to **Learning Center**.
- [ ] Review the postmortem verification form for `INC-001`.
- [ ] Click **💾 Confirm Resolution & Retain into Hindsight**.
- [ ] Verify the success confirmation banner and inspect the local audit timeline below.

### Step 6: 12-Case Benchmark Suite
- [ ] Navigate to **Evaluation Lab**.
- [ ] Click **▶ Run Full Benchmark Suite**.
- [ ] Verify:
  - Evaluates 12 cases across 7 dimensions with isolated ground truth.
  - Plotly dark bar chart renders comparisons across all 12 cases.
  - Shows +25.0 points gain on recurrent incidents and 100% failed fix avoidance.

