# OPSRECALL — 3-Minute Live Competition Demonstration Script

**Title**: OPSRECALL: Change-Aware Operational Memory for SRE Teams  
**Duration**: 3:00 Minutes  
**Target Scenario**: `INC-001` (Checkout API Latency Spike Post-Deployment) & Negative Control `EVAL-006` (Novel CDN Distractor)  
**Presenter**: Solo Builder / Principal AI Engineer  

---

### [00:00 - 00:30] Phase 1: The SRE Paradox & Live Dashboard Intro

**[Visual Cue]**:  
*Show browser at `http://localhost:8501`. Hero Section: Operational Command Center. Point to System Mode, Bank `opsrecall-demo`, and Monitored Service Health.*

**Speaker**:  
"At 3:00 AM, when production latency surges and error budgets burn, on-call SRE teams scramble to diagnose microservice failures. Invariably, teams guess. Someone suggests scaling container replicas or increasing client timeouts. 

What they don't know is that three months ago, during a similar incident on the checkout service, another engineer tried increasing that exact timeout—and it caused total thread starvation across the database pool. That postmortem was written, filed in Confluence, and forgotten.

This is why I built **OPSRECALL**. Our tagline is simple: *Every incident should make the next one easier to solve.*

OPSRECALL decouples persistent operational memory from reasoning. It uses **Vectorize Hindsight** as an intelligent operational memory bank and **Groq** for rapid structured reasoning."

---

### [00:30 - 01:25] Phase 2: Live Memory ON vs. Memory OFF Comparison

**[Visual Cue]**:  
*Click sidebar -> **AI Investigation & Comparison**.  
Select `INC-001 — Checkout API Latency Spike Post-Deployment`.  
Click **⚡ Run Side-by-Side Comparison**.*

**Speaker**:  
"Let's see this in action on `INC-001`: our checkout API has spiked to 8,500ms P99 latency and 504 timeouts following Helm deployment DEP-8492.

Let's run the investigation on identical telemetry through the exact same reasoning engine: on the left, **without memory**; on the right, **with Hindsight memory**."

**[Visual Cue]**:  
*Hover over the left column (WITHOUT Hindsight Memory).*

**Speaker**:  
"On the left, without historical memory, the model sees latency and guesses that database queries are slow or container replicas are insufficient. Its top recommendation? *Scale checkout-api pods or increase client timeouts.* In reality, increasing timeouts would worsen thread pool starvation."

**[Visual Cue]**:  
*Hover over the right column (WITH Hindsight Memory). Highlight the red alert box and green verified remedy.*

**Speaker**:  
"Now look at the right column, augmented with Hindsight memory. 

Look at this red alert callout: **🚫 DO NOT REPEAT FAILED MITIGATION**. It flags the past failed fix, warning the engineer that increasing timeouts previously caused catastrophic thread starvation.

Next, it identifies the exact verified root cause: the Helm deployment capped `max_db_connections` at 10 instead of 150. And it provides the verified remedy: hot-patch Helm values to 150 and rolling restart pods.

Persistent operational memory transformed a dangerous guess into an immediate, verified fix."

---

### [01:25 - 02:05] Phase 3: Negative Control & Distractor Rejection

**[Visual Cue]**:  
*In the incident selector, choose an unrelated scenario: `INC-003` (Payment Gateway TLS Expiration) or `EVAL-006` (CDN Edge 403 Forbidden).  
Click **Run Side-by-Side Comparison**.*

**Speaker**:  
"A critical question in operational memory is: *Does the system blindly force old memories onto new, unrelated outages?*

Here we test a novel failure mode: an edge certificate expiration. 

Notice that Hindsight does NOT hallucinate the connection-pool memory from `INC-001`. It evaluates the TLS handshake errors, rejects irrelevant historical precedents, and isolates the specific expired certificate. Hindsight's TEMPR retrieval accurately matches relevant context and rejects false precedents."

---

### [02:05 - 02:35] Phase 4: Human-in-the-Loop Learning Loop

**[Visual Cue]**:  
*Click sidebar -> **Learning Center**. Select `INC-001`. Show the postmortem verification form.*

**Speaker**:  
"Operational safety requires human verification. OPSRECALL never automatically commits unverified anomaly data to memory.

In the **Learning Center**, the on-call SRE reviews the actual verified root cause, logs what worked, and records what failed. 

When the engineer clicks **💾 Confirm Resolution & Retain into Hindsight**, the experience is structured with metadata tags and committed to Hindsight Cloud with a deterministic document ID to guarantee idempotency. Now, the next time this failure pattern occurs, the team is protected."

---

### [02:35 - 03:00] Phase 5: Quantitative Evaluation & Conclusion

**[Visual Cue]**:  
*Click sidebar -> **Evaluation Lab**. Display the 16-case benchmark chart and macro KPI cards.*

**Speaker**:  
"We validated this architecture across a rigorous 16-scenario benchmark across 16 evaluation dimensions with completely isolated ground truth. 

On recurrent incidents, Hindsight memory improves resolution scores by **+40.5 points** (59.5 to 100.0) with a **+25.0% lift in Top-1 accuracy** while flagging **100% of historical failed mitigations** and maintaining zero false recalls on novel edge cases.

Production outages are expensive tuition payments. With persistent operational memory, engineering teams only have to pay it once.

Thank you!"

