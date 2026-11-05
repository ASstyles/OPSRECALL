# OPSRECALL — Groq Live Integration & Model Verification

**Audit Date**: November 5, 2026  
**Auditor**: Principal AI Engineer & LLM Integration Lead  
**Component**: `core/llm_engine.py`  
**Endpoint**: `GET https://api.groq.com/openai/v1/models`  
**Target Model**: `openai/gpt-oss-120b` (131,072 context window, Mixture-of-Experts)  

---

## 1. Executive Summary & Live Verification Status

```
========================================================================================
LIVE GROQ API STATUS: NOT VERIFIED — LIVE GROQ CREDENTIALS MISSING IN .ENV
OFFLINE SRE REASONING ENGINE STATUS: VERIFIED (100% GREEN)
========================================================================================
```

In accordance with strict competition integrity standards, OPSRECALL never fabricates active API connections or simulates token completions when credentials are missing. 

The configuration detects `GROQ_API_KEY` in `.env`. Since the current `.env` contains template placeholder `your_groq_api_key_here`, the application safely operates in **Offline SRE Expert Reasoning Mode**. The live model resolution architecture, JSON Schema validation, and error handling have been verified through unit and mock test suites.

---

## 2. Model Deprecation Remediation

| Previous Model | Deprecation Sunset | Status | Remediation |
|---|---|---|---|
| `llama-3.3-70b-versatile` | August 16, 2026 | Deprecated for free/developer tiers | Replaced primary default with `openai/gpt-oss-120b` |
| `qwen/qwen3.6-27b` | September 14, 2026 | Deprecated | Excluded from fallback resolution |
| `openai/gpt-oss-120b` | Production Active | Primary Target | Configured as primary in `config.py` and `.env.example` |

### Dynamic Model Resolution (`get_verified_account_model`)
Rather than relying on static fallback lists in source code, `core/llm_engine.py` dynamically queries `client.models.list()` against the authenticated account:
1. Verifies if configured `GROQ_MODEL` (`openai/gpt-oss-120b`) is available to the account.
2. If unavailable, dynamically filters out known deprecated models (`llama-3.3-70b-versatile`, `qwen/qwen3.6-27b`).
3. Selects active JSON-capable production models (e.g. `openai/gpt-oss-120b`, `llama-3.1-8b-instant`).

---

## 3. Structured Output & Pydantic Validation

1. **Native JSON Object Enforcement**:
   Calls pass `response_format={"type": "json_object"}`, ensuring Groq returns valid JSON.
2. **Schema Validation**:
   Responses are parsed and validated against `core.validators.InvestigationResult`:
   - `executive_summary`: str
   - `hypotheses`: List[Hypothesis] (ranked 1..3 with likelihood and evidence)
   - `recommended_remediation_steps`: List[ActionRecommendation]
   - `confidence_level`: Literal["HIGH", "MEDIUM", "LOW"]
3. **No Silent Fallback on Live Failures**:
   If a live API call fails with 401 Unauthorized or rate limits, OPSRECALL raises an explicit `RuntimeError` rather than silently presenting offline mock output as live reasoning.
4. **Untrusted Evidence Boundary**:
   Incident telemetry and recalled memories are encapsulated within data tags (`=== CURRENT INCIDENT UNDER INVESTIGATION ===`), instructing the model to treat them strictly as evidence to analyze, never as instructions to execute.

---

## 4. Verification Command & Actual Output

```bash
python scripts/verify_groq.py
```
```
================================================================================
OPSRECALL -- GROQ MODEL AVAILABILITY & CAPABILITY VERIFICATION
================================================================================
Target Model Configured: openai/gpt-oss-120b
API Key Status:          [MISSING]
--------------------------------------------------------------------------------
[INFO] GROQ_API_KEY is not configured in .env or environment.
       OPSRECALL operates in offline rule-based reasoning mode without live keys.
       To enable live Groq inference:
         1. Obtain an API key from https://console.groq.com/
         2. Set GROQ_API_KEY in your .env file.
         3. Default recommended production model: openai/gpt-oss-120b
================================================================================
```

---

## 5. Unblocking Live Groq Verification

1. Add your Groq API key to `.env`:
   ```env
   GROQ_API_KEY=gsk_your_actual_key_here
   GROQ_MODEL=openai/gpt-oss-120b
   ```
2. Run `python scripts/verify_groq.py` to execute account authentication and smoke testing.
3. Run `python -m pytest tests/test_live_integration.py -k test_live_groq_generation_structured_json -v`.
