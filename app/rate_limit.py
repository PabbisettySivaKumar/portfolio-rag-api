import time
from collections import defaultdict

from fastapi import Request


class InMemoryRateLimiter:
    """Fixed-window per-key rate limiter. Per-process only (state lives in this
    container), which is fine for a single HF Space instance."""

    def __init__(self, requests_limit: int = 5, window_seconds: int = 60):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.history = defaultdict(list)

    def is_rate_limited(self, key: str) -> bool:
        now = time.time()
        # Clean up history for this key to prevent memory leaks
        self.history[key] = [t for t in self.history[key] if now - t < self.window_seconds]
        if len(self.history[key]) >= self.requests_limit:
            return True
        self.history[key].append(now)
        return False


def client_ip_from_request(request: Request) -> str:
    """Best-effort real client IP for rate-limit keying.

    Behind the HF Spaces proxy the socket peer is an internal address
    (10.16.x.x in the logs), so prefer the first X-Forwarded-For entry, which is
    the original client, and fall back to the socket peer only when absent.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if (request.client and request.client.host) else "unknown"
