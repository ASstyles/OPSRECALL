# OPSRECALL — Technical Limitations & Operational Boundaries

This document provides a candid, technically honest assessment of current limitations, trade-offs, and future work for OPSRECALL.

---

## 1. Simulated Infrastructure & Telemetry

- **No Real Production Binds**: In accordance with operational safety principles, OPSRECALL is evaluated on high-fidelity synthetic telemetry. It does not connect directly to live production cloud providers (AWS, GCP, Azure), Kubernetes clusters, or databases.
- **Pre-Packaged Metrics & Logs**: Metric graphs and error log excerpts are ingested from synthetic JSON schemas. In a production enterprise deployment, OPSRECALL would require stream collectors (e.g., Prometheus OpenMetrics, Datadog API, OpenTelemetry, Grafana Loki).

---

## 2. Advisory Scope & Operational Safety

- **Read-Only / Advisory Operation**: OPSRECALL deliberately does not execute shell commands, restart containers, or apply Kubernetes manifests. All diagnostic commands and remediation steps are advisory SOPs generated for review by human engineers.
- **Human Verification Requirement**: New experiences cannot be automatically committed to Hindsight without human verification in the Learning Center. While this protects memory quality against poisoning from temporary anomalies, it requires manual human intervention.

---

## 3. Asynchronous Memory Consolidation Latency

- **Hindsight Processing Time**: When retaining complex documents in Hindsight Cloud, extraction and graph consolidation operate asynchronously on the backend. When querying immediately after a retention request (`retain_async=False` or `True`), there may be a slight indexing delay (typically 1–3 seconds) before newly extracted entities appear in full TEMPR recall results. Bounded polling via `client.list_memories(bank_id, document_id)` is implemented for verification.
- **Offline Fallback Approximation**: When external credentials (`HINDSIGHT_API_KEY` or `GROQ_API_KEY`) are not provided, OPSRECALL utilizes a deterministic offline expert engine. While this guarantees that all tests, benchmarks, and UI demonstrations run smoothly without crashing, it is a local rule-based simulation and does not reflect real-time neural embedding retrieval.

---

## 4. Query Length & Context Limits

- **Log Truncation**: Production stack traces can exceed tens of thousands of lines. OPSRECALL currently extracts the most distinctive log snippets (top 6 lines or first 200 characters) to avoid overflowing LLM context windows or dilution of semantic recall signals. A production version would benefit from automated log deduplication and clustering (e.g., Drain3 log parsing) before query construction.
- **Bank-Level Isolation**: All demo incidents reside in a single bank (`opsrecall-demo`), while automated tests use `opsrecall-live-tests`. In a large multi-tenant enterprise, separate memory banks should be partitioned per organization, team, or critical domain (e.g., `checkout-domain`, `payment-vault-domain`).

---

## 5. Model Availability & Rate Limits

- **Groq Model Selection & Deprecations**: Groq announced deprecation of `llama-3.3-70b-versatile` effective August 16, 2026, for free and developer tiers. OPSRECALL defaults to `openai/gpt-oss-120b` (131k context window, MoE architecture, native structured JSON mode) with an automatic fallback cascade (`openai/gpt-oss-120b` -> `llama-3.3-70b-versatile` -> `llama-3.1-8b-instant`).
- **Groq Rate Limits**: Groq's developer tiers impose per-minute token and request limits. During rapid benchmark test runs with live Groq keys, bursts of concurrent requests may experience temporary rate-limit throttling. The client includes exponential retry backoff, but dedicated API quotas are recommended for heavy evaluation workloads.

---

## 6. Prompt Injection & Input Boundary Protections

- **Untrusted Telemetry Isolation**: Because incident logs may contain arbitrary external strings or attacker-crafted payloads (e.g., in HTTP User-Agent or query parameters), OPSRECALL fences all raw telemetry inside `<incident_telemetry_untrusted>` tags. System prompts instruct the LLM that content within these tags is inert telemetry to be diagnosed rather than instructions to execute.
- **Redaction Heuristics**: Automated regex filters strip JWT Bearer tokens, AWS secrets, and password fields. In high-security environments, enterprise data loss prevention (DLP) proxies should run upstream of the investigation layer.

---

## 7. BAND AI Desktop Competition Requirements & Execution Boundaries

- **Execution Model**: OPSRECALL is architected as a local Python-based application paired with a local Streamlit web application interface running on `http://localhost:8501`. In the BAND AI Desktop evaluation environment, the application executes locally via `python -m streamlit run app.py` on the Windows desktop host and renders directly within any local web browser or embedded desktop webview.
- **Port & Firewall Configuration**: Streamlit binds to local loopback (`127.0.0.1:8501`). No external ingress, inbound NAT, or public ports are required.
- **Desktop Runtime Dependencies**: Requires Python 3.10+ (tested on Python 3.14.3 Windows x64), SQLite 3 (standard library), and the dependencies listed in `requirements.txt`.
- **Offline / Isolated Execution Support**: In fully air-gapped or network-restricted desktop evaluation environments without internet access to external APIs (Hindsight Cloud or Groq Cloud), OPSRECALL's deterministic offline fallback engine activates automatically. All 7 dashboard views, incident comparisons, learning loops, and benchmark evaluations execute hermetically with zero external network calls.
- **Live Cloud Connectivity**: If outbound HTTPS (port 443) to `api.hindsight.vectorize.io` and `api.groq.com` is permitted in the desktop environment, supplying valid keys in `.env` activates real-time neural recall and LLM reasoning.
