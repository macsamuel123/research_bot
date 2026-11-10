"""In-memory sliding-window limiter for login attempts (per client IP, 60 s window)."""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta

WINDOW = timedelta(seconds=60)


class RateLimiter:
    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._hits: defaultdict[str, deque[datetime]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: datetime) -> bool:
        """Record an attempt; False when the key already used its budget in the window."""
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - WINDOW:
                hits.popleft()
            if len(hits) >= self._limit:
                return False
            hits.append(now)
            return True
