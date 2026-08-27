"""Lightweight demo rate-limiting and instance concurrency controls for FitForge Agent.

DESIGN & OPERATIONAL CHARACTERISTICS:
1. Single-Instance Demo Guard:
   - Tailored specifically for public evaluation on Google Cloud Run configured with
     max-instances=1, min-instances=0, and containerConcurrency=1.
   - It is an in-memory, process-local guard. It resets automatically on Cloud Run container
     cold starts or container recycling.
   - It is NOT a multi-region distributed rate limiter (such as Redis or Google Cloud Armor).

2. Privacy & Data Handling:
   - Client IP addresses are hashed using SHA-256 immediately upon receipt.
   - Raw IP strings are NEVER logged, returned in API errors, or persisted to memory/disk.
   - All internal tracking uses truncated 16-character SHA-256 hash keys.

3. Memory Bounding & Expiration Pruning:
   - Expired timestamp entries (> 2x cooldown window) are automatically pruned on every
     acquisition attempt, ensuring bounded memory footprint indefinitely.

4. Concurrency & Exemption:
   - Thread-safe mutual exclusion protects active workflow execution (max 1 concurrent run).
   - GET /health and static asset routes are strictly exempt from rate limiting.
"""

import hashlib
import logging
import threading
import time
from typing import Dict, Optional
from fastapi import HTTPException, Request, status

logger = logging.getLogger("fitforge.limiter")

COOLDOWN_SECONDS: int = 60
PRUNE_INTERVAL_SECONDS: int = 120


def _hash_client_id(raw_id: str) -> str:
    """Hash client identifier into a fixed-length privacy-safe key."""
    return hashlib.sha256(raw_id.strip().encode("utf-8")).hexdigest()[:16]


def extract_client_identifier(request: Request) -> str:
    """Safely extract client IP from X-Forwarded-For or client host.

    Extracts the leftmost (client) entry in the X-Forwarded-For chain when behind
    Google Cloud Load Balancer / Cloud Run ingress proxy. Returns a fallback identifier
    if headers are absent or malformed.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
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
        # Stores {hashed_client_key: timestamp}
        self._client_timestamps: Dict[str, float] = {}
        self._is_active: bool = False
        self._lock = threading.Lock()

    def _prune_expired(self, now: float) -> None:
        """Remove entries older than the retention threshold to maintain bounded memory."""
        cutoff = now - (self.cooldown_seconds * 2)
        expired_keys = [k for k, ts in self._client_timestamps.items() if ts < cutoff]
        for k in expired_keys:
            del self._client_timestamps[k]

    def acquire(self, client_id: str) -> None:
        """Attempt to acquire execution permission for a client.

        Raises:
            HTTPException(429): If the instance is busy or the client is within cooldown.
        """
        now = time.time()
        client_hash = _hash_client_id(client_id)

        with self._lock:
            # 1. Prune expired tracking records to bound memory usage
            self._prune_expired(now)

            # 2. Instance concurrency check (maximum 1 active execution per instance)
            if self._is_active:
                logger.info("Assessment rejected: instance busy (client_hash=%s)", client_hash[:8])
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="An assessment is currently being processed. Please wait a moment before submitting.",
                    headers={"Retry-After": "10"},
                )

            # 3. Per-client cooldown check
            last_request = self._client_timestamps.get(client_hash)
            if last_request is not None:
                elapsed = now - last_request
                if elapsed < self.cooldown_seconds:
                    retry_after = max(1, int(self.cooldown_seconds - elapsed))
                    logger.info(
                        "Assessment rejected: rate limited (client_hash=%s, retry_after=%ds)",
                        client_hash[:8],
                        retry_after,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded. Please wait {retry_after} seconds before submitting another workflow.",
                        headers={"Retry-After": str(retry_after)},
                    )

            # 4. Mark client timestamp and active execution flag
            self._client_timestamps[client_hash] = now
            self._is_active = True
            logger.info("Assessment accepted (client_hash=%s)", client_hash[:8])

    def release(self) -> None:
        """Release the active instance execution lock."""
        with self._lock:
            self._is_active = False

    def reset(self) -> None:
        """Reset internal state (for test suite isolation)."""
        with self._lock:
            self._client_timestamps.clear()
            self._is_active = False


# Global singleton limiter
rate_limiter = DemoRateLimiter()
