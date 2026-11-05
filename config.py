"""
Configuration module for OPSRECALL.
Centralizes environment variables, default settings, and system paths.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INCIDENTS_PATH = DATA_DIR / "incidents.json"
EVALUATION_CASES_PATH = DATA_DIR / "evaluation_cases.json"
EVALUATION_GROUND_TRUTH_PATH = DATA_DIR / "evaluation_ground_truth.json"
OUTPUTS_DIR = BASE_DIR / "outputs" / "evaluation_results"
ASSETS_DIR = BASE_DIR / "assets"
AUDIT_DIR = BASE_DIR / "outputs" / "audit"

# Ensure output directories exist
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables from .env if present
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE, override=True)
else:
    load_dotenv(override=True)


class Settings:
    """Application settings loaded from environment or defaults."""

    # Base Directory paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    INCIDENTS_PATH: Path = INCIDENTS_PATH
    EVALUATION_CASES_PATH: Path = EVALUATION_CASES_PATH
    EVALUATION_GROUND_TRUTH_PATH: Path = EVALUATION_GROUND_TRUTH_PATH
    OUTPUTS_DIR: Path = OUTPUTS_DIR
    ASSETS_DIR: Path = ASSETS_DIR
    AUDIT_DIR: Path = AUDIT_DIR

    # Hindsight Cloud Configuration
    HINDSIGHT_API_KEY: str = os.getenv("HINDSIGHT_API_KEY", "").strip()
    HINDSIGHT_BANK_ID: str = os.getenv("HINDSIGHT_BANK_ID", "opsrecall-demo").strip()
    HINDSIGHT_TEST_BANK_ID: str = os.getenv("HINDSIGHT_TEST_BANK_ID", "opsrecall-live-tests").strip()
    HINDSIGHT_BASE_URL: str = (
        os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io").strip()
        or "https://api.hindsight.vectorize.io"
    )

    # Groq LLM Configuration
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
    # Official recommended Groq production model (migrated from deprecated llama-3.3-70b-versatile)
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()

    # Application Persistence (SQLite for local audit logs and evaluation results)
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", str(BASE_DIR / "opsrecall.db")).strip()

    # Environment
    OPSRECALL_ENV: str = os.getenv("OPSRECALL_ENV", "development").strip()

    @classmethod
    def is_hindsight_configured(cls) -> bool:
        """Check whether Hindsight API credentials are provided."""
        return bool(cls.HINDSIGHT_API_KEY and len(cls.HINDSIGHT_API_KEY) > 5)

    @classmethod
    def is_groq_configured(cls) -> bool:
        """Check whether Groq API credentials are provided."""
        return bool(cls.GROQ_API_KEY and len(cls.GROQ_API_KEY) > 5)


settings = Settings()
