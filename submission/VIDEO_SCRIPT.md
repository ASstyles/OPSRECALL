# OPSRECALL — Video Demonstration Script (3–4 Minutes)

**Title**: OPSRECALL: Change-Aware Operational Memory for SRE Teams  
**Format**: Screen capture walkthrough with voiceover  
**Estimated Run Time**: ~3:30 minutes  

---

### [00:00 - 00:35] Act 1: The Problem & Introduction

**[ON-SCREEN CUE]**:  
*Show Streamlit Dashboard Command Center (`http://localhost:8501`). Dark charcoal theme, metrics visible: 5 Incidents, Bank `opsrecall-demo` active, SEV-1 counts, monitored services.*

**SPEAKER**:  
"It's 3:00 AM. A critical production service spikes in latency, clients receive 504 timeouts, and error budgets burn. On-call engineers scramble to diagnose the failure. 

Inevitably, someone suggests scaling pod replicas or increasing timeout thresholds. What they don't know is that two months ago, during a similar outage, another engineer tried that exact fix—and it caused total thread starvation across the database pool. 

That postmortem was written, filed in Confluence, and forgotten.

This is why I built **OPSRECALL**. Our tagline is simple: *Every incident should make the next one easier to solve.* 

OPSRECALL decouples persistent operational memory from reasoning. It uses **Vectorize Hindsight** as an intelligent memory bank and **Groq** for high-speed, structured SRE reasoning."

---

### [00:35 - 01:25] Act 2: Telemetry Ingestion & Hindsight Architecture

**[ON-SCREEN CUE]**:  
*Click sidebar -> Navigate to **Architecture & About**. Display the system architecture diagram showing Streamlit -> Investigation Controller -> Hindsight Memory Bank & Groq LLM -> Evidence Layer -> Human Verification loop.*

**SPEAKER**:  
"Unlike traditional document search, OPSRECALL captures **change-aware operational memory**. 

Most incidents are triggered by state changes: a Helm chart update, a certificate expiration, or a cache TTL modification. 

OPSRECALL uses three core Hindsight operations:
1. **`retain`**: Ingests verified incidents with stable document IDs, indexing telemetry, deployment changes, verified root causes, and crucially: *failed mitigation attempts*.
2. **`recall`**: Uses Hindsight's multi-strategy TEMPR search to retrieve relevant historical experiences in milliseconds when new symptoms emerge.
3. **`reflect`**: Synthesizes macro operational patterns across months of postmortems to detect recurring configuration drift before outages happen."

---

### [01:25 - 02:35] Act 3: Live Memory ON vs. Memory OFF Comparison

**[ON-SCREEN CUE]**:  
*Click sidebar -> Navigate to **AI Investigation & Comparison**.  
Select `INC-001 — Checkout API Latency Spike Post-Deployment`.  
Click the primary button: **`Run Side-by-Side Comparison`**.*

**SPEAKER**:  
"Let's see this in action with a live side-by-side comparison.

We take `INC-001`: our checkout API has surged to 8500ms P99 latency and 504 timeouts following Helm deployment DEP-8492.

Let's run the investigation through the exact same Groq `llama-3.3-70b` model: on the left, **without memory**; on the right, **with Hindsight memory**."

**[ON-SCREEN CUE]**:  
*Hover over the left column (Without Hindsight). Highlight the generic hypotheses and the bad recommendation.*

**SPEAKER**:  
"On the left, without historical memory, the model sees high latency and guesses that database queries are slow or container replicas are insufficient. Its top recommendation? *Scale checkout-api pods or increase client timeouts.* 

In reality, doing that would worsen thread starvation."

**[ON-SCREEN CUE]**:  
*Hover over the right column (With Hindsight). Highlight the red alert box: `DO NOT REPEAT: Increased checkout-api HTTP client timeout` and the green verified remediation box: `Restore max_db_connections in Helm values to 150`.*

**SPEAKER**:  
"Now look at the right column, powered by Hindsight. 

First: it immediately matches the symptoms and Helm change to past precedent `INC-001`. 

Second: look at this red callout: **DO NOT REPEAT**. It flags the past failed fix, warning the engineer that increasing timeouts previously exacerbated thread pool starvation.

Third: it identifies the exact verified root cause: the Helm deployment capped `max_db_connections` at 10 instead of 150. And it gives the verified remediation: hot-patch Helm values to 150 and roll restart.

Having persistent operational memory turned a dangerous recommendation into an immediate, verified fix."

---

### [02:35 - 03:05] Act 4: The Learning Loop & Evaluation Lab

**[ON-SCREEN CUE]**:  
*Click sidebar -> Navigate to **Learning Center**. Show the verification form and historical postmortem records.  
Then click **Evaluation Lab**. Show the benchmark bar chart comparing Memory OFF (66.7) vs Memory ON (100.0).*

**SPEAKER**:  
"OPSRECALL enforces strict operational safety. It is an advisory tool—it never runs destructive commands. 

In the **Learning Center**, engineers verify the actual root cause and successful mitigation before retaining new experience into Hindsight.

In our **Evaluation Lab**, we run reproducible benchmarks across 6 test scenarios, including distractors. 

On recurrent incidents, memory-enabled investigations score +40 points higher than baseline, specifically because they avoid historical failed fixes. And on novel distractor cases, Hindsight correctly avoids false recalls."

---

### [03:05 - 03:30] Act 5: Summary & Conclusion

**[ON-SCREEN CUE]**:  
*Return to Command Center or Architecture page. Show repository details.*

**SPEAKER**:  
"Production outages are expensive tuition payments. Engineering teams shouldn't have to pay them twice. 

By coupling Vectorize Hindsight's persistent operational memory with fast LLM reasoning, OPSRECALL ensures every incident genuinely makes the next one easier to solve.

The entire codebase, test suite, and evaluation reports are live on GitHub. Thank you!"

**[FADE OUT]**

