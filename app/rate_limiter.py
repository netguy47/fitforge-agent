"""Lightweight demo rate-limiting and instance concurrency controls for FitForge Agent.

NOTE: This is an in-memory single-instance demonstration safeguard designed for
public hackathon/demo evaluations on Google Cloud Run (concurrency=1, max-instances=1).
It is NOT a distributed production-grade rate limiter (such as Redis or Cloud Armor).
"""

import hashlib
import logging
import threading
import time
from typing import Dict, Optional, Tuple
from fastapi import HTTPException, Request, status

logger = logging.getLogger("fitforge.limiter")

COOLDOWN_SECONDS: int = 60


def _mask_ip(ip: str) -> str:
    """Return a privacy-preserving truncated SHA-256 hash prefix of an IP address."""
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:8]


def extract_client_identifier(request: Request) -> str:
    """Safely extract client IP from X-Forwarded-For or client host without trusting spoofed headers."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # First entry in X-Forwarded-For chain represents the original client
        client_ip = forwarded_for.split(",")[0].strip()
        if client_ip:
            return client_ip
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


class DemoRateLimiter:
    """In-memory rate limiter and single-instance execution guard."""

    def __init__(self, cooldown_seconds: int = COOLDOWN_SECONDS):
        self.cooldown_seconds = cooldown_seconds
        self._client_timestamps: Dict[str, float] = {}
        self._is_active: bool = False
        self._lock = threading.Lock()

    def acquire(self, client_id: str) -> None:
        """Attempt to acquire execution permission for a client.

        Raises:
            HTTPException(429): If the instance is busy or the client is within cooldown.
        """
        now = time.time()
        masked_id = _mask_ip(client_id)

        with self._lock:
            # 1. Instance concurrency check (maximum 1 active execution per instance)
            if self._is_active:
                logger.info("Assessment rejected: instance busy (client_hash=%s)", masked_id)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="An assessment is currently being processed. Please wait a moment before submitting.",
                    headers={"Retry-After": "10"},
                )

            # 2. Per-client cooldown check
            last_request = self._client_timestamps.get(client_id)
            if last_request is not None:
                elapsed = now - last_request
                if elapsed < self.cooldown_seconds:
                    retry_after = max(1, int(self.cooldown_seconds - elapsed))
                    logger.info(
                        "Assessment rejected: rate limited (client_hash=%s, retry_after=%ds)",
                        masked_id,
                        retry_after,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded. Please wait {retry_after} seconds before submitting another workflow.",
                        headers={"Retry-After": str(retry_after)},
                    )

            # 3. Mark client timestamp and active execution flag
            self._client_timestamps[client_id] = now
            self._is_active = True
            logger.info("Assessment accepted (client_hash=%s)", masked_id)

    def release(self) -> None:
        """Release the active instance execution lock."""
        with self._lock:
            self._is_active = False

    def reset(self) -> None:
        """Reset internal state (for testing purposes)."""
        with self._lock:
            self._client_timestamps.clear()
            self._is_active = False


# Global singleton limiter
rate_limiter = DemoRateLimiter()
