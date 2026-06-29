import hmac

from fastapi import APIRouter, Header, HTTPException, status

from app.config import settings
from app.rag.neo4j_client import get_driver

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/health/neo4j")
async def neo4j_keepalive(authorization: str = Header(default="")) -> dict[str, str]:
    if not settings.keepalive_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Neo4j keepalive is not configured",
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
