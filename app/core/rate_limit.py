"""Small in-memory rate limiter for the public API (single process)."""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:

    def __init__(self, per_minute: int, daily_cap: int = 0, clock=time.time):
        self.per_minute = per_minute
        self.daily_cap = daily_cap
        self.clock = clock
        self._hits: dict[str, deque] = defaultdict(deque)
        self._day = None
        self._day_count = 0
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, str]:
        """Return (allowed, reason). Records the hit when allowed."""
        now = self.clock()
        day = int(now // 86400)

        with self._lock:
            if day != self._day:
                self._day = day
                self._day_count = 0

            if self.daily_cap and self._day_count >= self.daily_cap:
                return False, "The daily demo limit has been reached. Please try again tomorrow."

            if self.per_minute:
                hits = self._hits[key]
                while hits and now - hits[0] >= 60:
                    hits.popleft()
                if len(hits) >= self.per_minute:
                    return False, "Too many requests. Please wait a minute and try again."
                hits.append(now)

            self._day_count += 1
            return True, ""
