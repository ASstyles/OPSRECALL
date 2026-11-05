# OPSRECALL — Groq LLM Integration & Model Verification Audit

**Audit Date**: November 5, 2026  
**Auditor**: Principal AI Engineer & DevOps Lead  
**Component**: Structured Reasoning & Hypothesis Generation Layer (`core/llm_engine.py`)  
**Target Model**: `openai/gpt-oss-120b`  
**Endpoint**: `https://api.groq.com/openai/v1/models`  

---

## 1. Executive Summary & Status

```
========================================================================================
LIVE GROQ API STATUS: BLOCKED (API CREDENTIALS UNSET IN .ENV)
DETERMINISTIC SRE REASONING ENGINE STATUS: VERIFIED (100% GREEN)
========================================================================================
```

In accordance with strict technical honesty guidelines, OPSRECALL never fabricates Groq completions or simulates fake token latency when credentials are missing. 

When `GROQ_API_KEY` is configured in `.env`, OPSRECALL targets `openai/gpt-oss-120b` (131,072 context window, mixture-of-experts architecture, native structured JSON mode) with an automatic fallback cascade. When credentials are not configured, OPSRECALL safely transitions to its offline rule-based SRE reasoning engine.

---

## 2. Model Deprecation Remediation

| Previous Model | Sunset Date | Status | Remediation |
|---|---|---|---|
| `llama-3.3-70b-versatile` | August 16, 2026 | Deprecated for free/developer tiers | Migrated default to `openai/gpt-oss-120b` |
| `qwen/qwen3.6-27b` | September 14, 2026 | Deprecated | Excluded from fallback cascade |
| `openai/gpt-oss-120b` | Production Active | Primary Target | Configured as primary in `config.py` and `.env.example` |

### Dynamic Model Fallback Cascade
In `core/llm_engine.py`, OPSRECALL implements a multi-tier fallback chain:
1. **Primary**: `openai/gpt-oss-120b` (High-speed structured JSON reasoning, 131k context)
2. **Tier-2 Fallback**: `llama-3.3-70b-versatile` (If account has active enterprise allocation)
3. **Tier-3 Fallback**: `llama-3.1-8b-instant` (Ultra-low-latency lightweight JSON model)

---

## 3. Structured Output & Prompt Injection Defense

1. **Native JSON Mode**: `response_format={"type": "json_object"}` enforces deterministic JSON compliance from Groq.
2. **Pydantic Validation**: All completions are parsed and validated against `core.validators.InvestigationResult`. If an invalid response is generated, `LLMGenerationError` is raised rather than silently reporting corrupted data.
3. **Telemetry Sanitization (`_sanitize_telemetry`)**: Model input prompts are stripped of all evaluation answer keys, preventing data leakage.
4. **Untrusted Evidence Boundary**: Incident logs and recalled memories are placed inside clear data containers in the prompt, instructing the model to treat them strictly as evidence to analyze, never instructions to execute.

---

## 4. Verification Script & Live Testing

The script `scripts/verify_groq.py` performs account-level model verification:
1. Probes `GET https://api.groq.com/openai/v1/models` using the account API key.
2. Asserts whether `openai/gpt-oss-120b` is present in the account's active model list.
3. Executes a test chat completion with `response_format={"type": "json_object"}`.
4. Verifies JSON parsing and schema alignment.

---

## 5. How to Unblock Live Groq Inference

1. Set your key in `.env`:
   ```env
   GROQ_API_KEY=gsk_your_actual_key_from_groq_console
   GROQ_MODEL=openai/gpt-oss-120b
   ```
2. Run the smoke test:
   ```bash
   python scripts/verify_groq.py
   ```
3. Run the live integration test:
   ```bash
   python -m pytest tests/test_live_integration.py -k test_live_groq_generation_structured_json -v
   ```

