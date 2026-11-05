# Why Every Incident Should Make the Next One Easier: Building OPSRECALL with Hindsight

*By Aviral Srivastava*

---

## The 03:00 AM Paradox

Every site reliability engineer knows the 03:00 AM pager alert feeling. A downstream payment gateway degrades, thread pools saturate, latency skyrockets, and error budgets evaporate. Within minutes, multiple engineers jump on an incident bridge. 

Under pressure, teams invariably do what humans under stress do: they guess. Someone suggests increasing the HTTP client timeout from 5 seconds to 30 seconds. Someone else scales the container replica count. 

Neither realizes that three months ago, during a nearly identical incident on the checkout service, another engineer tried increasing that exact timeout—and it caused total thread starvation across the database connection pool. The postmortem was written, filed in Confluence, and forgotten.

This is the central paradox of incident management: **Engineering teams spend hundreds of hours writing postmortems, yet every incident bridge begins from zero.**

To solve this, I designed and built **OPSRECALL**, an advisory operational intelligence agent that uses **Vectorize Hindsight** as persistent operational memory coupled with **Groq** for rapid structured reasoning. The goal is simple: ensure that every incident genuinely makes the next one faster, safer, and easier to resolve.

---

## Memory vs. Reasoning: Why RAG Is Not Enough

Traditional Retrieval-Augmented Generation (RAG) approaches to incident management fail for three primary reasons:

1. **Document-Level Chunking**: RAG slices postmortems into arbitrary 500-token chunks. A chunk containing symptoms might be detached from the section detailing what failed or the exact configuration parameter that fixed it.
2. **Lack of Change Awareness**: Incidents are almost always precipitated by state changes—deployments, config drift, certificate renewals, or schema migrations. Standard vector embeddings fail to connect a subtle Helm values tweak to an upstream latency spike.
3. **Absence of Negative Experience**: Knowing what *not* to do is often more critical during an outage than knowing what to do. Traditional search retrieves relevant documents, but standard LLMs still recommend intuitive yet disastrous actions (like flushing a Redis cache during a cache stampede).

OPSRECALL addresses this by treating memory and reasoning as distinct architectural layers:

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
|        opsrecall-demo            |         |     llama-3.3-70b-versatile      |
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

*[Screenshot Placeholder: OPSRECALL Operational Command Center & Telemetry Console]*

---

## Implementing Hindsight: Retain, Recall, and Reflect

Integrating the official `hindsight-client` SDK into Python was the core of this project. Rather than treating Hindsight as an opaque vector database, OPSRECALL uses its native operational primitives: `retain`, `recall`, and `reflect`.

### 1. Change-Aware Retention

When an incident is resolved and verified by an engineer, OPSRECALL structures the incident experience to capture context, symptoms, change details, attempted mitigations, and explicit failures:

```python
# From core/memory_manager.py
def format_incident_for_retention(incident: Incident) -> str:
    lines = [
        f"=== INCIDENT RECORD: {incident.incident_id} ===",
        f"Title: {incident.incident_title}",
        f"Service: {incident.affected_service}",
        f"Severity: {incident.severity}",
        f"Timestamp: {incident.incident_timestamp}",
        "",
        "OPERATIONAL SYMPTOMS:",
    ]
    for s in incident.symptoms:
        lines.append(f"- {s}")
    
    if incident.deployment_id or incident.deployment_or_change:
        lines.append(f"DEPLOYMENT & CHANGE CONTEXT: {incident.deployment_or_change}")

    if incident.failed_mitigation_attempts:
        lines.append("FAILED MITIGATION ATTEMPTS (DO NOT REPEAT):")
        for f in incident.failed_mitigation_attempts:
            lines.append(f"- FAILED FIX: {f}")

    if incident.successful_mitigation:
        lines.append(f"SUCCESSFUL RESOLUTION: {incident.successful_mitigation}")

    return "\n".join(lines)
```

The memory is committed to the dedicated `opsrecall-demo` bank using stable document IDs to guarantee idempotency:

```python
# From core/hindsight_client.py
response = client.retain(
    bank_id="opsrecall-demo",
    content=formatted_content,
    document_id=incident.incident_id,
    metadata={"service": incident.affected_service, "severity": incident.severity},
    tags=[incident.affected_service, incident.severity.lower(), "incident-experience"],
    timestamp=incident.incident_timestamp,
)
```

Because Hindsight utilizes TEMPR (combining semantic similarity, keyword matching, entity resolution, and temporal reasoning), it doesn't just store text; it indexes entities, timelines, and causal connections.

### 2. Targeted Recall During Triage

When a new incident occurs, the triage engine synthesizes the symptoms, logs, and deployment events into a high-signal search query:

```python
query = memory_manager.build_recall_query(
    service=service,
    symptoms=symptoms,
    error_logs=error_logs,
    deployment_change=deployment_change,
)
memories = client.recall(bank_id="opsrecall-demo", query=query, budget="mid")
```

The returned `RecallResult` objects provide direct provenance: memory ID, source incident ID, text, and relevance scores.

### 3. Extracting Negative Experience

Before sending evidence to the reasoning engine, OPSRECALL isolates historical failed fixes:

```python
# From core/memory_manager.py
def extract_failed_approaches(recalled_memories: List[RecalledMemoryItem]) -> List[FailedApproachWarning]:
    warnings = []
    for mem in recalled_memories:
        if "failed" in mem.text.lower():
            for line in mem.text.splitlines():
                if "failed" in line.lower() and len(line.strip()) > 10:
                    warnings.append(FailedApproachWarning(
                        approach=line.strip(),
                        why_failed="Identified as unsuccessful in prior incident investigation.",
                        historical_source_incident=mem.source_incident_id or "Historical Record"
                    ))
    return warnings
```

---

## Side-by-Side: Proving the Value of Memory

To verify whether persistent memory truly changes operational outcomes, I built a side-by-side comparison mode in the Streamlit UI. The user can feed identical telemetry into the same underlying LLM (`llama-3.3-70b-versatile` via Groq) under two conditions:

1. **Memory DISABLED**: Telemetry only. No Hindsight context.
2. **Memory ENABLED**: Telemetry + Hindsight recalled experiences.

*[Screenshot Placeholder: Side-by-Side Comparison UI showing Memory OFF vs Memory ON]*

### The Results on INC-001 (Connection Pool Starvation Post-Helm Deployment):

- **Without Hindsight**: The LLM noted high P99 latency (8500ms) and connection timeouts. It hypothesized slow database queries or insufficient container replicas. Its top remediation recommendation: *"Scale checkout-api pods horizontally or increase request timeout thresholds."*
- **With Hindsight**: The LLM immediately matched the pattern to `INC-001`. It warned: **"DO NOT REPEAT: Increased checkout-api HTTP client timeout from 5s to 15s (Exacerbated thread starvation)."** Instead, it pinpointed the exact root cause: the Helm chart had inadvertently lowered `max_db_connections` from 150 to 10. The recommendation: *"Restore max_db_connections in Helm values to 150 and rolling restart pods."*

Having persistent operational memory transformed a recommendation that would have worsened the outage into a precise, verified resolution in seconds.

---

## Quantitative Evaluation

To ensure technical rigor, I created an automated evaluation framework testing 6 synthetic scenarios: 5 operational recurrences (connection pool starvation, worker capacity reduction, TLS expiration, cache stampede, and third-party gateway timeouts) and 1 novel distractor (CDN S3 bucket IAM policy 403).

The benchmark grades results on:
1. Top-3 root cause accuracy.
2. Expected historical incident matching.
3. Recall of past failed mitigations.
4. Avoidance of previously unsuccessful fixes in recommendations.
5. Resistance to false recall on distractors.

### Benchmark Results:

```
================================================================================
Case ID    | Service                   | Distractor | Mem OFF   | Mem ON    | Delta  
--------------------------------------------------------------------------------
EVAL-001   | checkout-api              | No         | 60.0      | 100.0     | +40.0  
EVAL-002   | order-fulfillment-worker  | No         | 60.0      | 100.0     | +40.0  
EVAL-003   | payment-gateway           | No         | 60.0      | 100.0     | +40.0  
EVAL-004   | catalog-service           | No         | 60.0      | 100.0     | +40.0  
EVAL-005   | checkout-orchestrator     | No         | 60.0      | 100.0     | +40.0  
EVAL-006   | cdn-edge                  | Yes        | 100.0     | 100.0     | +0.0   
================================================================================
Macro Composite Score: Memory OFF: 66.7 / 100  |  Memory ON: 100.0 / 100 (+33.3 pts)
Failed Mitigation Avoidance: Memory OFF: 0% flagged  |  Memory ON: 100% flagged
```

On novel distractor scenarios (`cdn-edge`), both modes scored 100%, proving that Hindsight avoids hallucinatory false recalls when an incident has no historical precedent. But on recurrent incidents, Memory ON outperformed Memory OFF by **+40.0 points**, specifically because it prevented the engineer from repeating known failed mitigations.

---

## Operational Safety and Limitations

OPSRECALL is an advisory assistant, not an autonomous agent executing commands in production. 

1. **No Destructive Execution**: It generates standard operating procedure (SOP) diagnostic queries and remediation steps for human engineers to review.
2. **Human Verification**: Newly learned operational experiences are only retained into Hindsight after an engineer verifies the resolution in the Learning Center.
3. **Untrusted Telemetry**: Raw logs and metrics are treated strictly as untrusted data to analyze, never as executable instructions.

While OPSRECALL demonstrates the power of change-aware operational memory, it currently operates on simulated infrastructure. Connecting it to live enterprise telemetry (Datadog, Prometheus, Grafana Loki) and integrating GitOps automated postmortem ingestion represent the natural next steps.

---

## Conclusion

Incident postmortems are too valuable to sit in cold document storage. By coupling **Vectorize Hindsight's** persistent memory with rapid LLM reasoning, OPSRECALL turns past operational pain into active real-time protection.

Every production outage is an expensive tuition payment. With persistent memory, engineering teams only have to pay it once.

---
*The complete, runnable code repository, test suite, and evaluation results are available on GitHub.*

