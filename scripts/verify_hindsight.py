"""
Verification script for Hindsight connection.
Checks SDK installation, credentials, cloud connectivity, and memory bank status.
Usage:
    python scripts/verify_hindsight.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from core.hindsight_client import get_hindsight_client


def main() -> int:
    print("==================================================")
    print("OPSRECALL — HINDSIGHT CONNECTION VERIFICATION")
    print("==================================================")
    print(f"Base URL: {settings.HINDSIGHT_BASE_URL}")
    print(f"Bank ID:  {settings.HINDSIGHT_BANK_ID}")
    print(f"API Key:  {'[CONFIGURED]' if settings.is_hindsight_configured() else '[MISSING]'}")
    print("--------------------------------------------------")

    client = get_hindsight_client()
    health = client.check_health()

    status = health.get("status")
    mode = health.get("mode")
    message = health.get("message")
    version = health.get("version")
    bank_exists = health.get("bank_exists")

    print(f"Status:      {status}")
    print(f"Mode:        {mode}")
    print(f"Version:     {version or 'N/A'}")
    print(f"Bank Active: {'Yes' if bank_exists else 'No'}")
    print("--------------------------------------------------")
    print(f"Diagnostics: {message}")
    print("==================================================")

    if status == "CONNECTED":
        print("[OK] Hindsight Cloud memory is verified and ready for live investigations.")
        return 0
    elif status == "NOT_CONFIGURED":
        print("[INFO] Hindsight API key is missing. The application will operate in offline preview mode.")
        print("       To enable live Hindsight memory, set HINDSIGHT_API_KEY in your .env file.")
        return 0
    else:
        print("[FAIL] Could not verify Hindsight connection. Please check your credentials or network.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

