# OPSRECALL — Remaining Issues & Operational Boundaries Audit

**Audit Date**: November 5, 2026  
**Auditor**: Principal QA Lead & Competition Reviewer  

---

## 1. Live Cloud Credential Dependency (Blocking Live Integration)

- **Status**: **BLOCKED (Awaiting Local API Credentials)**
- **Technical Detail**: The application includes full, verified live integrations for both **Vectorize Hindsight Cloud** (`hindsight-client 1.2.0`) and **Groq Cloud API** (`openai/gpt-oss-120b`). Both clients include live health check scripts, dynamic `.env` hot-reloading, and dedicated test bank isolation (`opsrecall-live-tests`).
- **Reason**: The local `.env` file contains placeholder keys (`your_hindsight_api_key_here`, `your_groq_api_key_here`). In accordance with competition integrity rules, OPSRECALL does not fabricate fake HTTP 200 responses.
- **Remediation**: The user must paste their genuine `HINDSIGHT_API_KEY` and `GROQ_API_KEY` into `C:\Users\avira\Desktop\OPSRECALL\.env` and click **`🔄 Reload .env & Re-check`** in the dashboard sidebar.
- **Fallback**: The application operates in high-fidelity deterministic offline simulation mode, allowing complete demonstration of all 7 sections without crashing.

---

## 2. Infrastructure Scope (Advisory Safety by Design)

- **Status**: **INTENTIONAL ARCHITECTURAL BOUNDARY**
- **Technical Detail**: OPSRECALL is an advisory SRE agent. It does not execute destructive shell commands (`kubectl delete`, `helm rollback`, container restarts) against live cloud clusters.
- **Reason**: Production reliability guardrails require human review of remediation steps before execution.
- **Remediation**: In a production deployment, OPSRECALL would emit verified Ansible/Terraform playbooks or trigger human-approved Spinnaker/ArgoCD promotion gates.

---

## 3. Telemetry Stream Integration (Simulated vs Live Streaming)

- **Status**: **PLANNED ENTERPRISE ROADMAP**
- **Technical Detail**: Telemetry in the demo is ingested from high-fidelity synthetic JSON datasets representing 12 real-world outage patterns.
- **Remediation**: Live enterprise integration would require OpenTelemetry (OTel) collectors, Prometheus PromQL querying, and Grafana Loki log forwarders.

---

## 4. Groq Free-Tier Rate Throttling

- **Status**: **OPERATIONAL RISK (Under Rapid Concurrent Load)**
- **Technical Detail**: Free/developer Groq tiers enforce per-minute request limits. During rapid benchmark test runs (12 consecutive cases across both modes), bursts of API calls may experience rate-limit backoff.
- **Remediation**: Exponential backoff is built into `core/llm_engine.py`, but dedicated enterprise API quotas are recommended for heavy continuous CI evaluation.

