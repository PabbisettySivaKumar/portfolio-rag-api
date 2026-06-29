import hmac
import time
from collections import defaultdict

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.config import settings
from app.rag.neo4j_client import get_driver

router = APIRouter(tags=["health"])


class InMemoryRateLimiter:
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


# Limit to 5 keepalive requests per minute per IP
keepalive_limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=60)


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/health/neo4j")
async def neo4j_keepalive(
    request: Request,
    authorization: str = Header(default=""),
) -> dict[str, str]:
    if not settings.keepalive_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Neo4j keepalive is not configured",
        )

    # Rate limit by client IP
    client_ip = request.client.host if (request.client and request.client.host) else "unknown"
    if keepalive_limiter.is_rate_limited(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )

    expected = f"Bearer {settings.keepalive_token}"
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid keepalive token",
        )

    result = await get_driver().execute_query("RETURN 1 AS alive")
    if not result.records or result.records[0]["alive"] != 1:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Neo4j keepalive query failed",
        )

    return {"status": "ok", "database": "connected"}
