import hmac

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.config import settings
from app.rag.neo4j_client import get_driver
from app.rate_limit import InMemoryRateLimiter, client_ip_from_request

router = APIRouter(tags=["health"])

# Limit to 5 keepalive requests per minute per IP
keepalive_limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=60)


@router.get("/health")
def health_check(verbose: bool = False) -> dict[str, str]:
    if verbose:
        return {"status": "ok", "detail": "all systems operational"}
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
    client_ip = client_ip_from_request(request)
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
