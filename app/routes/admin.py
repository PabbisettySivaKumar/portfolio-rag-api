import asyncio
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, status

from app.config import settings
from app.rag.ingest import MissingIngestEnv, ingest_content

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)

# Serialize ingestion so a manual re-ingest can't overlap another run (manual or
# the background startup ingest sharing the same Neo4j driver).
_ingest_lock = asyncio.Lock()


def _require_admin(authorization: str) -> None:
    """Gate admin routes behind the KEEPALIVE_TOKEN bearer token."""
    if not settings.keepalive_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin endpoints are not configured (KEEPALIVE_TOKEN unset)",
        )
    expected = f"Bearer {settings.keepalive_token}"
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token",
        )


@router.get("/config")
async def effective_config(authorization: str = Header(default="")) -> dict:
    """Report the non-sensitive effective config the container actually loaded,
    for diagnostics (e.g. confirming FRONTEND_ORIGIN / CORS). Token-guarded; no
    secrets are returned."""
    _require_admin(authorization)
    return {
        "frontend_origin_raw": settings.frontend_origin,
        "frontend_origins": settings.frontend_origins,
        "rag_top_k": settings.rag_top_k,
        "rag_min_score": settings.rag_min_score,
        "chat_model": settings.litellm_chat_model,
        "langfuse_enabled": settings.langfuse_enabled,
    }


@router.post("/ingest")
async def trigger_ingest(
    force: bool = False,
    authorization: str = Header(default=""),
) -> dict:
    """Sync content/*.md into Neo4j on demand.

    Incremental by default; pass ``?force=true`` to re-chunk and re-embed every
    file regardless of its hash (e.g. after changing the chunking logic). Guarded
    by the KEEPALIVE_TOKEN bearer token and serialized against concurrent runs.
    """
    _require_admin(authorization)

    if _ingest_lock.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An ingestion is already in progress",
        )

    async with _ingest_lock:
        try:
            summary = await ingest_content(force=force, log=logger)
        except MissingIngestEnv as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            )
        except Exception:
            logger.exception("Manual ingestion failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ingestion failed; see server logs",
            )

    return {"status": "ok", "force": force, **summary}
