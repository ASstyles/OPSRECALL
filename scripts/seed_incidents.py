"""
Seed script for OPSRECALL historical incidents.
Seeds verified historical incidents into Hindsight Cloud and SQLite local repository.
Safe to rerun: utilizes stable `document_id` matching each incident ID (INC-001..INC-005)
to prevent duplicate document entries in Hindsight.
Usage:
    python scripts/seed_incidents.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from core.incident_engine import get_incident_engine
from core.memory_manager import get_memory_manager


def main() -> int:
    print("==================================================")
    print("OPSRECALL — INCIDENT DATASET SEEDING")
    print("==================================================")
    print(f"Target Hindsight Bank: {settings.HINDSIGHT_BANK_ID}")
    print(f"Hindsight Live Config: {'Configured' if settings.is_hindsight_configured() else 'Unconfigured (Offline Cache Only)'}")
    print("--------------------------------------------------")

    engine = get_incident_engine()
    mm = get_memory_manager()
    incidents = engine.get_all_incidents()

    print(f"Found {len(incidents)} historical incidents in dataset.\n")

    retained_count = 0
    for inc in incidents:
        print(f"Processing {inc.incident_id}: {inc.incident_title}")
        print(f"  Service:  {inc.affected_service} ({inc.severity})")
        print(f"  Root Cause: {inc.actual_verified_root_cause[:70]}...")

        # Retain via MemoryManager
        res = mm.retain_incident(inc)
        success = res.get("success", False)
        mode = res.get("mode", "UNKNOWN")
        op_id = res.get("operation_id")

        if success and mode == "LIVE_HINDSIGHT":
            retained_count += 1
            print(f"  -> Retained to Hindsight Cloud! [Op ID: {op_id or 'sync'}]")
        elif mode == "OFFLINE_UNCONFIGURED":
            print("  -> Saved to local SQLite cache (Hindsight credentials not configured).")
        else:
            print(f"  -> Retention status: {mode} ({res.get('message', '')})")
        print()

    print("==================================================")
    if settings.is_hindsight_configured():
        print(f"[SUCCESS] {retained_count}/{len(incidents)} incidents successfully retained in Hindsight memory bank '{settings.HINDSIGHT_BANK_ID}'.")
    else:
        print(f"[INFO] {len(incidents)} incidents verified in local SQLite database.")
        print("       Configure HINDSIGHT_API_KEY in .env to sync directly to Hindsight Cloud.")
    print("==================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())

