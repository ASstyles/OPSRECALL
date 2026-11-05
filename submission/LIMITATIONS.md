# OPSRECALL — Technical Limitations & Operational Boundaries

This document provides a candid, technically honest assessment of current limitations, trade-offs, and future work for OPSRECALL.

---

## 1. Simulated Infrastructure & Telemetry

- **No Real Production Binds**: In accordance with competition rules and operational safety principles, OPSRECALL is evaluated on high-fidelity synthetic telemetry. It does not connect directly to live production cloud providers (AWS, GCP, Azure), Kubernetes clusters, or databases.
- **Pre-Packaged Metrics & Logs**: Metric graphs and error log excerpts are ingested from synthetic JSON schemas. In a production enterprise deployment, OPSRECALL would require stream collectors (e.g., Prometheus OpenMetrics, Datadog API, OpenTelemetry, Grafana Loki).

---

## 2. Advisory Scope & Operational Safety

- **Read-Only / Advisory Operation**: OPSRECALL deliberately does not execute shell commands, restart containers, or apply Kubernetes manifests. All diagnostic commands and remediation steps are advisory SOPs generated for review by human engineers.
- **Human Verification Requirement**: New experiences cannot be automatically committed to Hindsight without human verification in the Learning Center. While this protects memory quality against poisoning from temporary anomalies, it requires manual human intervention.

---

## 3. Asynchronous Memory Consolidation Latency

- **Hindsight Processing Time**: When retaining complex documents in Hindsight Cloud, extraction and graph consolidation operate asynchronously on the backend. When querying immediately after a retention request (`retain_async=False` or `True`), there may be a slight indexing delay (typically 1–3 seconds) before newly extracted entities appear in full TEMPR recall results.
- **Offline Fallback Approximation**: When external credentials (`HINDSIGHT_API_KEY` or `GROQ_API_KEY`) are not provided, OPSRECALL utilizes a deterministic offline expert engine. While this guarantees that all tests, benchmarks, and UI demonstrations run smoothly without crashing, it is a local rule-based simulation and does not reflect real-time neural embedding retrieval.

---

## 4. Query Length & Context Limits

- **Log Truncation**: Production stack traces can exceed tens of thousands of lines. OPSRECALL currently extracts the most distinctive log snippets (top 6 lines or first 200 characters) to avoid overflowing LLM context windows or dilution of semantic recall signals. A production version would benefit from automated log deduplication and clustering (e.g., Drain3 log parsing) before query construction.
- **Bank-Level Isolation**: All demo incidents reside in a single bank (`opsrecall-demo`). In a large multi-tenant enterprise, separate memory banks should be partitioned per organization, team, or critical domain (e.g., `checkout-domain`, `payment-vault-domain`).

---

## 5. Model Availability & Rate Limits

- **Groq Rate Limits**: Groq's free and developer tiers impose per-minute token and request limits. During rapid benchmark test runs with live Groq keys, bursts of concurrent requests may experience temporary rate-limit throttling. The client includes exponential retry backoff, but dedicated API quotas are recommended for heavy evaluation workloads.

---

## 6. Known Incomplete Functionality / Future Roadmap

- **Autonomous GitOps Ingestion**: Automatically scraping closed GitHub Pull Requests and merged Helm commits to ingest deployment changes without manual input.
- **Automated Postmortem Parsing**: Ingesting unstructured Markdown or PDF postmortems directly from Jira or Confluence via webhook.
- **Continuous Background Reflection**: Scheduling recurring cron jobs using Hindsight's `reflect` API to automatically email weekly systemic fragility digests to SRE leads.

