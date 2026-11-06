"""
Configuration module for OPSRECALL.
Centralizes environment variables, default settings, and system paths.
Provides reliable .env discovery, dynamic reloading, and safe diagnostics.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import find_dotenv, load_dotenv

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


def find_and_load_env() -> Path | None:
    """
    Search for and load .env file from:
    1. Explicit OPSRECALL_ENV_FILE environment variable
    2. Project root (BASE_DIR / ".env")
    3. Current Working Directory (Path.cwd() / ".env")
    4. Parent directories via find_dotenv
    """
    candidates = []

    custom_path = os.getenv("OPSRECALL_ENV_FILE")
    if custom_path:
        candidates.append(Path(custom_path).resolve())

    candidates.append(BASE_DIR / ".env")
    candidates.append(Path.cwd() / ".env")

    for c in candidates:
        if c.exists() and c.is_file():
            load_dotenv(dotenv_path=c, override=True)
            return c

    # Fallback to standard dotenv search
    dotenv_str = find_dotenv(usecwd=True)
    if dotenv_str:
        p = Path(dotenv_str).resolve()
        load_dotenv(dotenv_path=p, override=True)
        return p

    return None


# Initial load
_CURRENT_ENV_FILE = find_and_load_env()


def mask_secret(val: str) -> str:
    """Safely mask API keys without exposing secrets."""
    if not val:
        return "[UNCONFIGURED]"
    val_clean = val.strip()
    if val_clean.lower() in (
        "your_hindsight_api_key_here",
        "your_groq_api_key_here",
        "your_api_key_here",
        "placeholder",
        "none",
        "null",
        "",
    ):
        return "[PLACEHOLDER - NOT SET]"
    if len(val_clean) <= 8:
        return "••••••••"
    return f"{val_clean[:4]}...{val_clean[-4:]}"


class Settings:
    """Application settings loaded from environment or defaults with dynamic reloading."""

    # Base Directory paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    INCIDENTS_PATH: Path = INCIDENTS_PATH
    EVALUATION_CASES_PATH: Path = EVALUATION_CASES_PATH
    EVALUATION_GROUND_TRUTH_PATH: Path = EVALUATION_GROUND_TRUTH_PATH
    OUTPUTS_DIR: Path = OUTPUTS_DIR
    ASSETS_DIR: Path = ASSETS_DIR
    AUDIT_DIR: Path = AUDIT_DIR

    @classmethod
    def reload(cls) -> Path | None:
        """Reload environment variables from .env and update state."""
        global _CURRENT_ENV_FILE
        _CURRENT_ENV_FILE = find_and_load_env()
        return _CURRENT_ENV_FILE

    @classmethod
    def get_env_file_path(cls) -> Path | None:
        """Return path to currently detected .env file if any."""
        global _CURRENT_ENV_FILE
        if _CURRENT_ENV_FILE and _CURRENT_ENV_FILE.exists():
            return _CURRENT_ENV_FILE
        return find_and_load_env()

    # Hindsight Cloud Configuration
    @property
    def HINDSIGHT_API_KEY(self) -> str:
        key = os.getenv("HINDSIGHT_API_KEY", "").strip()
        if key.lower() in ("your_hindsight_api_key_here", "your_api_key_here", "placeholder"):
            return ""
        return key

    @property
    def HINDSIGHT_BANK_ID(self) -> str:
        return os.getenv("HINDSIGHT_BANK_ID", "opsrecall-demo").strip() or "opsrecall-demo"

    @property
    def HINDSIGHT_TEST_BANK_ID(self) -> str:
        return os.getenv("HINDSIGHT_TEST_BANK_ID", "opsrecall-live-tests").strip() or "opsrecall-live-tests"

    @property
    def HINDSIGHT_BASE_URL(self) -> str:
        url = os.getenv("HINDSIGHT_API_URL", "").strip() or os.getenv("HINDSIGHT_BASE_URL", "").strip()
        return url if url else "https://api.hindsight.vectorize.io"

    @property
    def HINDSIGHT_API_URL(self) -> str:
        """Alias for HINDSIGHT_BASE_URL."""
        return self.HINDSIGHT_BASE_URL

    # Groq LLM Configuration
    @property
    def GROQ_API_KEY(self) -> str:
        key = os.getenv("GROQ_API_KEY", "").strip()
        if key.lower() in ("your_groq_api_key_here", "your_api_key_here", "placeholder"):
            return ""
        return key

    @property
    def GROQ_MODEL(self) -> str:
        return os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip() or "openai/gpt-oss-120b"

    # Application Persistence
    @property
    def SQLITE_DB_PATH(self) -> str:
        return os.getenv("SQLITE_DB_PATH", str(BASE_DIR / "opsrecall.db")).strip()

    # Operational Settings
    @property
    def OPSRECALL_ENV(self) -> str:
        return os.getenv("OPSRECALL_ENV", "development").strip()

    def is_hindsight_configured(self) -> bool:
        """Check whether genuine Hindsight API credentials are provided."""
        key = self.HINDSIGHT_API_KEY
        return bool(key and len(key) > 5 and not key.lower().startswith("your_"))

    def is_groq_configured(self) -> bool:
        """Check whether genuine Groq API credentials are provided."""
        key = self.GROQ_API_KEY
        return bool(key and len(key) > 5 and not key.lower().startswith("your_"))

    def get_diagnostics(self) -> dict[str, Any]:
        """Return safe, non-confidential configuration diagnostics."""
        env_path = self.get_env_file_path()
        hs_raw = os.getenv("HINDSIGHT_API_KEY", "")
        gr_raw = os.getenv("GROQ_API_KEY", "")

        return {
            "env_file_found": bool(env_path and env_path.exists()),
            "env_file_path": str(env_path) if env_path else None,
            "hindsight_configured": self.is_hindsight_configured(),
            "hindsight_key_status": mask_secret(hs_raw),
            "hindsight_bank_id": self.HINDSIGHT_BANK_ID,
            "hindsight_test_bank_id": self.HINDSIGHT_TEST_BANK_ID,
            "hindsight_base_url": self.HINDSIGHT_BASE_URL,
            "groq_configured": self.is_groq_configured(),
            "groq_key_status": mask_secret(gr_raw),
            "groq_model": self.GROQ_MODEL,
            "sqlite_db_path": self.SQLITE_DB_PATH,
            "environment": self.OPSRECALL_ENV,
        }


# Global singleton settings instance
settings = Settings()
