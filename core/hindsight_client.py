"""
Hindsight Client wrapper for OPSRECALL.
Integrates with the official `hindsight-client` Python SDK.
Provides robust connection health checks, memory bank creation/verification,
bounded asynchronous indexing waits, and typed interfaces for RETAIN, RECALL, and REFLECT operations.
"""

from __future__ import annotations

import logging
import time
from typing import Any

# Official Hindsight Client and Models
from hindsight_client import (
    Hindsight,
    RecallResponse,
    ReflectResponse,
    RetainResponse,
)
from hindsight_client_api.exceptions import (
    ApiException,
    NotFoundException,
    UnauthorizedException,
)

from config import settings

logger = logging.getLogger("opsrecall.hindsight")


class HindsightClientWrapper:
    """Wrapper around the official Hindsight SDK with error handling, latency metrics, and health checks."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        bank_id: str | None = None,
        test_bank_id: str | None = None,
    ):
        self._explicit_base_url = base_url
        self._explicit_api_key = api_key
        self._explicit_bank_id = bank_id
        self._explicit_test_bank_id = test_bank_id
        self._client: Hindsight | None = None

    @property
    def base_url(self) -> str:
        url = self._explicit_base_url or settings.HINDSIGHT_BASE_URL
        return url.rstrip("/") if url else "https://api.hindsight.vectorize.io"

    @property
    def api_key(self) -> str:
        return self._explicit_api_key or settings.HINDSIGHT_API_KEY

    @property
    def bank_id(self) -> str:
        return self._explicit_bank_id or settings.HINDSIGHT_BANK_ID

    @property
    def test_bank_id(self) -> str:
        return self._explicit_test_bank_id or settings.HINDSIGHT_TEST_BANK_ID

    @property
    def is_configured(self) -> bool:
        """Check whether genuine Hindsight API credentials are provided."""
        if self._explicit_api_key is not None:
            return bool(
                self._explicit_api_key
                and len(self._explicit_api_key) > 5
                and not self._explicit_api_key.lower().startswith("your_")
            )
        return settings.is_hindsight_configured()

    def reset(self) -> None:
        """Reset internal client instance to pick up new configuration."""
        self._client = None

    def get_client(self) -> Hindsight:
        """Retrieve client or initialize if credentials now exist."""
        if not self.is_configured:
            raise RuntimeError("Hindsight client is not configured. Please set HINDSIGHT_API_KEY in your .env file.")
        if self._client is None:
            try:
                self._client = Hindsight(
                    base_url=self.base_url,
                    api_key=self.api_key,
                    timeout=30.0,
                    user_agent="OPSRECALL-Incident-Agent/2.0",
                )
            except Exception as e:
                logger.error(f"Failed to initialize Hindsight SDK client: {e}")
                self._client = None
                raise
        return self._client

    def check_health(self) -> dict[str, Any]:
        """Perform a genuine health check with roundtrip latency against Hindsight Cloud."""
        if not self.is_configured:
            env_file = settings.get_env_file_path()
            env_msg = (
                f".env file detected at '{env_file}', but HINDSIGHT_API_KEY is not set."
                if env_file
                else "No .env file found in project root. Copy .env.example to .env to configure credentials."
            )
            return {
                "status": "NOT_CONFIGURED",
                "mode": "UNCONFIGURED",
                "bank_id": self.bank_id,
                "base_url": self.base_url,
                "version": None,
                "bank_exists": False,
                "latency_ms": None,
                "message": (
                    f"HINDSIGHT_API_KEY is not configured. {env_msg} "
                    "OPSRECALL is operating in Offline Preview Mode with simulated operational memories."
                ),
            }

        start_time = time.time()
        try:
            client = self.get_client()

            # 1. Check API Version
            version_str = "connected"
            try:
                version_info = client.get_version()
                version_str = getattr(version_info, "version", str(version_info))
            except Exception as v_err:
                logger.warning(f"Could not retrieve Hindsight version: {v_err}")

            # 2. Verify or create dedicated bank
            bank_exists = False
            try:
                client.get_bank_profile(self.bank_id)
                bank_exists = True
            except NotFoundException:
                logger.info(f"Bank '{self.bank_id}' not found. Creating dedicated bank...")
                client.create_bank(
                    bank_id=self.bank_id,
                    name="OPSRECALL Operational Memory Bank",
                    reflect_mission=(
                        "OPSRECALL Incident Memory Bank: Store and recall operational SRE incidents, "
                        "deployment change records, failed mitigations, and verified resolutions."
                    ),
                )
                bank_exists = True

            latency_ms = round((time.time() - start_time) * 1000, 1)

            return {
                "status": "CONNECTED",
                "mode": "LIVE",
                "bank_id": self.bank_id,
                "base_url": self.base_url,
                "version": version_str,
                "bank_exists": bank_exists,
                "latency_ms": latency_ms,
                "message": f"Successfully connected to Hindsight Cloud ({latency_ms}ms). Memory bank '{self.bank_id}' is active.",
            }

        except UnauthorizedException as auth_err:
            return {
                "status": "AUTHENTICATION_FAILED",
                "mode": "ERROR",
                "bank_id": self.bank_id,
                "base_url": self.base_url,
                "version": None,
                "bank_exists": False,
                "latency_ms": None,
                "message": f"Hindsight authentication rejected (401 Unauthorized): {auth_err}",
            }
        except ApiException as api_err:
            return {
                "status": "API_ERROR",
                "mode": "ERROR",
                "bank_id": self.bank_id,
                "base_url": self.base_url,
                "version": None,
                "bank_exists": False,
                "latency_ms": None,
                "message": f"Hindsight API returned an error: {api_err}",
            }
        except Exception as ex:
            return {
                "status": "CONNECTION_FAILED",
                "mode": "ERROR",
                "bank_id": self.bank_id,
                "base_url": self.base_url,
                "version": None,
                "bank_exists": False,
                "latency_ms": None,
                "message": f"Could not reach Hindsight server at {self.base_url}: {ex}",
            }

    def ensure_bank_exists(self, bank_id: str | None = None) -> bool:
        """Ensure the target memory bank exists; create it if missing."""
        target_bank = bank_id or self.bank_id
        client = self.get_client()
        try:
            client.get_bank_profile(target_bank)
            return True
        except NotFoundException:
            client.create_bank(
                bank_id=target_bank,
                name="OPSRECALL Incident Bank",
                reflect_mission="Store operational incidents, root causes, failed mitigations, and resolutions.",
            )
            return True
        except Exception as e:
            logger.error(f"Error ensuring bank exists: {e}")
            raise

    def wait_for_document_processing(
        self,
        document_id: str,
        bank_id: str | None = None,
        timeout_seconds: float = 15.0,
        poll_interval: float = 1.5,
    ) -> bool:
        """
        Bounded polling for Hindsight asynchronous indexing.
        Polls client.list_memories until memory units for document appear or timeout.
        Returns True if indexed, False if timeout.
        """
        if not self.is_configured:
            return False

        target_bank = bank_id or self.bank_id
        client = self.get_client()
        start = time.time()

        while time.time() - start < timeout_seconds:
            try:
                res = client.list_memories(
                    bank_id=target_bank,
                    document_id=document_id,
                    limit=5,
                )
                total = getattr(res, "total", 0)
                items = getattr(res, "items", [])
                if (total is not None and total > 0) or (items is not None and len(items) > 0):
                    return True
            except Exception as e:
                logger.debug(f"Polling list_memories error for {document_id}: {e}")
            time.sleep(poll_interval)

        return False

    def retain(
        self,
        content: str,
        document_id: str | None = None,
        metadata: dict[str, str] | None = None,
        tags: list[str] | None = None,
        timestamp: str | None = None,
        bank_id: str | None = None,
        retain_async: bool = False,
    ) -> RetainResponse:
        """Store incident experience into Hindsight memory bank."""
        client = self.get_client()
        target_bank = bank_id or self.bank_id

        # Clean metadata dictionary so values are strings
        clean_metadata = {k: str(v) for k, v in (metadata or {}).items()}

        response = client.retain(
            bank_id=target_bank,
            content=content,
            document_id=document_id,
            metadata=clean_metadata,
            tags=tags or [],
            timestamp=timestamp,
            retain_async=retain_async,
        )
        return response

    def recall(
        self,
        query: str,
        max_tokens: int = 4096,
        budget: str = "mid",
        tags: list[str] | None = None,
        tags_match: str = "any",
        bank_id: str | None = None,
    ) -> RecallResponse:
        """Recall relevant historical operational memories via semantic & TEMPR search."""
        client = self.get_client()
        target_bank = bank_id or self.bank_id

        # Pass supported arguments to official SDK recall
        kwargs: dict[str, Any] = {
            "bank_id": target_bank,
            "query": query,
            "max_tokens": max_tokens,
            "budget": budget,
        }
        if tags:
            kwargs["tags"] = tags
            kwargs["tags_match"] = tags_match

        response = client.recall(**kwargs)
        return response

    def reflect(
        self,
        query: str,
        budget: str = "mid",
        context: str | None = None,
        bank_id: str | None = None,
    ) -> ReflectResponse:
        """Generate high-level operational reflections and recurring pattern analyses."""
        client = self.get_client()
        target_bank = bank_id or self.bank_id

        response = client.reflect(
            bank_id=target_bank,
            query=query,
            budget=budget,
            context=context,
        )
        return response


_hindsight_wrapper_instance: HindsightClientWrapper | None = None


def get_hindsight_client(force_reload: bool = False) -> HindsightClientWrapper:
    """Singleton getter for HindsightClientWrapper with optional reload."""
    global _hindsight_wrapper_instance
    if _hindsight_wrapper_instance is None or force_reload:
        if _hindsight_wrapper_instance is not None:
            _hindsight_wrapper_instance.reset()
        _hindsight_wrapper_instance = HindsightClientWrapper()
    return _hindsight_wrapper_instance
