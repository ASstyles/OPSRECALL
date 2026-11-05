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
  *Expected Output: `26 passed, 3 skipped` with 0 failures.*

---

## Live Demo Sequence (5–7 Minutes)

### Step 1: Verify System & Hindsight Health via CLI
```bash
python scripts/verify_hindsight.py
```
- **What to verify**:
  - Reports Base URL (`https://api.hindsight.vectorize.io`) and Bank ID (`opsrecall-demo`).
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
  - Select `INC-001`.
  - Review the verified resolution, root cause, and failed approaches.
  - Click **`Confirm Resolution & Retain into Hindsight`**.
- **What to highlight**:
  - Green confirmation banner showing retention into Hindsight bank `opsrecall-demo` with operation ID.
  - Audit record saved to local SQLite database.

---

### Step 8: Reproducible Benchmark in Evaluation Lab (Dashboard Tab 6)
- **Actions**:
  - Select **`Evaluation Lab`**.
  - Click **`Run Full Benchmark Suite`**.
- **What to highlight**:
  - Real-time execution across 6 benchmark cases (5 recurrences + 1 distractor).
  - Plotly bar chart comparing Memory OFF vs Memory ON scores per case.
  - Points out that on distractor case `EVAL-006` (`cdn-edge`), both score 100% (no false hallucination), while on recurrent outages, Memory ON delivers a +40 point advantage by preventing failed fixes.

---

### Step 9: Architecture Review (Dashboard Tab 7)
- **Actions**:
  - Select **`Architecture & About`**.
  - Show the generated architecture diagram (`assets/architecture.png`).
  - Reiterate the core philosophy: *Hindsight is memory; LLM is reasoning. Decoupling them enables enterprise-grade operational resilience.*

