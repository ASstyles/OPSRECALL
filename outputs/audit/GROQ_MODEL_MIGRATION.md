# GROQ MODEL MIGRATION & CAPABILITY REPORT

**Date**: November 5, 2026  
**Auditor**: Principal AI Engineer  
**Status**: Remediated & Verified  

---

## 1. Context & Motivation

Groq announced deprecation and shutdown dates for older models on free and developer tiers, notably:
- `llama-3.3-70b-versatile`: Scheduled shutdown effective August 16, 2026 for free/developer tier users.
- `qwen/qwen3.6-27b`: Scheduled shutdown effective September 14, 2026.

Using a deprecated default model introduces high risk during competition evaluations if an account is on standard or developer quotas.

---

## 2. Selected Replacement Model: `openai/gpt-oss-120b`

Official Groq documentation (`https://console.groq.com/docs/models`) designates **`openai/gpt-oss-120b`** as the flagship open-weight MoE reasoning model on Groq hardware:
- **Parameters**: 120 billion total parameters.
- **Context Window**: 131,072 tokens.
- **Max Completion**: 65,536 tokens.
- **Speed**: ~500 tokens/sec on Groq LPUs.
- **Structured Output**: Native support for JSON mode (`response_format={"type": "json_object"}`).

---

## 3. Implemented Fallback Chain

To guarantee high availability and backward compatibility across different account tiers, OPSRECALL implements a multi-candidate fallback chain:

1. **Primary**: `openai/gpt-oss-120b` (Default in `config.py` and `.env.example`).
2. **Secondary**: `llama-3.3-70b-versatile` (Preserved for enterprise committed-spend contracts).
3. **Tertiary**: `llama-3.1-8b-instant` (High-speed fallback for resource-constrained tiers).

---

## 4. Engineering Changes

1. **Configurable Model**: `GROQ_MODEL` is configurable in `.env` with `openai/gpt-oss-120b` as verified default.
2. **Live Model Verification Script**: Added [scripts/verify_groq.py](file:///c:/Users/avira/Desktop/OPSRECALL/scripts/verify_groq.py) which:
   - Queries `GET https://api.groq.com/openai/v1/models`.
   - Validates model availability for the authenticated account.
   - Executes a test structured JSON completion.
   - Never logs or leaks the API token.
3. **Fail-Fast & Non-Silent Behavior**: If live Groq credentials are provided and fail, `core/llm_engine.py` raises an explicit `RuntimeError` rather than silently masking live API failures as offline reasoning.
4. **Ground-Truth Sanitization**: Implemented `_sanitize_telemetry()` to strictly strip any evaluation answer keys before prompt generation.
