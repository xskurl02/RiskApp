"""Small, dependency-free in-memory rate limiter.

Used for /login as a basic protection against credential stuffing.

Important:
  - This limiter is per-process. In production with multiple workers, enforce
    rate limits at the edge (reverse proxy) or use a shared store like Redis.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class InMemorySlidingWindowLimiter:
    """Represent In Memory Sliding Window Limiter."""

    def __init__(self, *, limit: int, window_s: int) -> None:
        """Internal helper for init."""
        self.limit = int(limit)
        self.window_s = int(window_s)
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def reset(self) -> None:
        """Clear all tracked keys (useful for tests)."""
        with self._lock:
            self._hits.clear()

    def check(self, key: str) -> tuple[bool, int]:
        """Check if the key is allowed.

        Returns:
            (allowed, retry_after_seconds)
        """
        now = time.monotonic()
        with self._lock:
            q = self._hits.get(key)
            if q is None:
                q = deque()
                self._hits[key] = q

            # prune
            cutoff = now - self.window_s
            while q and q[0] < cutoff:
                q.popleft()

            if len(q) >= self.limit:
                retry_after = max(1, int(q[0] + self.window_s - now))
                return False, retry_after

            q.append(now)
            return True, 0
