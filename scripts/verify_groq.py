"""
Groq Model Verification and Smoke Test Script for OPSRECALL.
Queries the live Groq models endpoint (GET https://api.groq.com/openai/v1/models),
verifies model availability for the configured account, tests JSON mode support,
and validates structured reasoning output.
Usage:
    python scripts/verify_groq.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings


def main() -> int:
    print("================================================================================")
    print("OPSRECALL -- GROQ MODEL AVAILABILITY & CAPABILITY VERIFICATION")
    print("================================================================================")
    print(f"Target Model Configured: {settings.GROQ_MODEL}")
    print(f"API Key Status:          {'[CONFIGURED]' if settings.is_groq_configured() else '[MISSING]'}")
    print("--------------------------------------------------------------------------------")

    if not settings.is_groq_configured():
        print("[INFO] GROQ_API_KEY is not configured in .env or environment.")
        print("       OPSRECALL operates in offline rule-based reasoning mode without live keys.")
        print("       To enable live Groq inference:")
        print("         1. Obtain an API key from https://console.groq.com/")
        print("         2. Set GROQ_API_KEY in your .env file.")
        print("         3. Default recommended production model: openai/gpt-oss-120b")
        print("================================================================================")
        return 0

    try:
        from groq import Groq, AuthenticationError, APIError

        client = Groq(api_key=settings.GROQ_API_KEY)

        # 1. Query models endpoint
        print("1. Querying Groq Account Models Endpoint (GET /openai/v1/models)...")
        models_page = client.models.list()
        available_model_ids = [m.id for m in models_page.data]

        print(f"   -> Retrieved {len(available_model_ids)} available models.")
        print(f"   -> Sample available models: {', '.join(available_model_ids[:6])}")

        target_model = settings.GROQ_MODEL

        # Check if target model is available
        if target_model in available_model_ids:
            print(f"   -> [OK] Configured model '{target_model}' is available to this account.")
            selected_model = target_model
        else:
            print(f"   -> [WARN] Configured model '{target_model}' not found in account model list.")
            # Check recommended non-deprecated alternatives
            deprecated_tokens = ["llama-3.3-70b-versatile", "qwen/qwen3.6-27b"]
            valid_candidates = [
                m for m in available_model_ids
                if not any(dep in m for dep in deprecated_tokens)
            ]
            selected_model = None
            for c in ["openai/gpt-oss-120b", "llama-3.1-8b-instant"]:
                if c in valid_candidates:
                    selected_model = c
                    print(f"   -> Automatically selected active candidate: '{selected_model}'")
                    break

            if not selected_model and valid_candidates:
                selected_model = valid_candidates[0]
                print(f"   -> Falling back to first non-deprecated model: '{selected_model}'")

        # 2. Run Smoke Test with JSON Mode
        print(f"\n2. Testing Structured JSON Chat Completion with '{selected_model}'...")
        test_messages = [
            {"role": "system", "content": "You are a test assistant. You must respond with a JSON object containing 'status' and 'model'."},
            {"role": "user", "content": "Ping test: confirm operational readiness."}
        ]

        response = client.chat.completions.create(
            model=selected_model,
            messages=test_messages,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=200,
        )

        content = response.choices[0].message.content
        parsed = json.loads(content)
        print(f"   -> [OK] Live completion succeeded!")
        print(f"   -> Model used: {response.model}")
        print(f"   -> Structured JSON parsed: {parsed}")
        print("--------------------------------------------------------------------------------")
        print("[SUCCESS] Groq integration verified and ready for live investigations.")
        print("================================================================================")
        return 0

    except AuthenticationError as auth_err:
        print(f"[FAIL] Groq Authentication Rejected (401 Unauthorized): {auth_err}")
        print("       Please verify that your GROQ_API_KEY in .env is valid.")
        print("================================================================================")
        return 1
    except APIError as api_err:
        print(f"[FAIL] Groq API Error: {api_err}")
        print("================================================================================")
        return 1
    except Exception as ex:
        print(f"[FAIL] Unexpected error during Groq verification: {ex}")
        print("================================================================================")
        return 1


if __name__ == "__main__":
    sys.exit(main())
