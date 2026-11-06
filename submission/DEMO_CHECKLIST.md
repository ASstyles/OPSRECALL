# OPSRECALL — Live Demonstration Checklist

This checklist provides a step-by-step sequence for judges and engineers to repeatably demonstrate the entire OPSRECALL workflow from terminal to web dashboard.

---

## Pre-Flight Setup (2 Minutes)

- [ ] **Clone & Environment**:
  ```bash
  cd OPSRECALL
  pip install -r requirements.txt
  ```
- [ ] **Configure API Keys** (Optional for Live Mode):
  - Copy `.env.example` to `.env`
  - Add `HINDSIGHT_API_KEY` and `GROQ_API_KEY`
  - *Note: If keys are omitted, OPSRECALL runs in fully functional Offline Preview Mode.*

- [ ] **Run Automated Test Suite**:
  ```bash
  python -m pytest -q
  ```
  *Expected Output: `42 passed, 3 skipped` with 0 failures.*

- [ ] **Verify Model and Memory Endpoints**:
  ```bash
  python scripts/verify_groq.py
  python scripts/verify_hindsight.py
  ```

---

## Live Demo Sequence (5–7 Minutes)

### Step 1: Verify System & Hindsight Health via CLI
```bash
python scripts/verify_hindsight.py
```
- **What to verify**:
  - Reports Base URL (`https://api.hindsight.vectorize.io`) and Bank ID (`opsrecall-demo` / `opsrecall-live-tests`).
  - Displays genuine status: `CONNECTED` (if key set) or `NOT_CONFIGURED` (in offline mode).
  - Never fabricates a false connected status.

---

### Step 2: Seed the Operational Incident Dataset
```bash
python scripts/seed_incidents.py
```
- **What to verify**:
  - Ingests 5 synthetic historical incidents (`INC-001` through `INC-005`).
  - Shows each incident's service, severity, change context, and failed fixes.
  - Safe to rerun: uses stable `document_id` matching `incident_id` to prevent duplicate retention.

---

### Step 3: Launch the Enterprise Streamlit Dashboard
```bash
streamlit run app.py
```
- Open `http://localhost:8501` in your browser.
- **Visual Check**:
  - Dark charcoal theme (`#0b0f19`) with cyan/blue accents and deep navy cards.
  - Sidebar shows active bank (`opsrecall-demo`) and system mode badge.

---

### Step 4: Explore the Command Center (Dashboard Tab 1)
- **Actions**:
  - Inspect top metric cards: Total Incidents (5), Monitored Services, SEV-1 count (3).
  - Review the Monitored Service Health table (`checkout-api`, `payment-gateway`, `catalog-service`, etc.).
  - Observe recent investigation audit logs.

---

### Step 5: Live Side-by-Side Comparison (Dashboard Tab 3)
*This is the core differentiator of the application.*
- **Actions**:
  - In the sidebar, select **`AI Investigation & Comparison`**.
  - Select `INC-001 — Checkout API Latency Spike Post-Deployment`.
  - Click the primary button: **`Run Side-by-Side Comparison`**.
- **What to highlight**:
  - **Left Column (Memory Disabled)**: Generic hypotheses (slow queries, container under-provisioning). Top recommendation is to increase client timeouts or scale pods.
  - **Right Column (Memory Enabled)**:
    1. Grounded in precedent `INC-001`.
    2. Red Alert Callout: **`DO NOT REPEAT: Increased checkout-api HTTP client timeout`** (avoids past failed fix).
    3. Pinpoints true root cause: Helm deployment lowered `max_db_connections` from 150 to 10.
    4. Recommends verified fix: Hot-patch Helm values to 150 and roll restart.
  - Point out the delta scorecard at the bottom.

---

### Step 6: Memory Explorer (Dashboard Tab 4)
- **Actions**:
  - Select **`Memory Explorer`**.
  - Enter query: `checkout-api 504 gateway timeout database pool`.
  - Click **`Search Memories`**.
- **What to highlight**:
  - Displays actual retrieved `RecallResult` records with relevance scores, tags, and document references.
  - Demonstrates semantic + change retrieval working together.

---

### Step 7: Incident Learning Loop (Dashboard Tab 5)
- **Actions**:
  - Select **`Learning Center`**.
  - Select an active incident or submit a new resolution for `INC-001`.
  - Provide human verification and click **`Confirm & Retain in Memory`**.
- **What to highlight**:
  - Experience is formatted with structured metadata and committed to Hindsight.
  - Shows that human SRE verification is required before operational memory is updated.

---

### Step 8: Multi-Dimensional Evaluation Lab (Dashboard Tab 6)
- **Actions**:
  - Select **`Evaluation Lab`**.
  - Click **`Run Benchmark Evaluation`**.
- **What to highlight**:
  - Evaluates 16 scenarios across 16 distinct dimensions with complete ground-truth anti-leakage isolation.
  - Shows +25.0% Top-1 root cause accuracy gain, +100.0% relevance retrieval gain, and +40.5 points improvement on recurrent incident resolution.
