import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.models import FeedbackRequest
from app.rag import observability as obs
from app.routes.health import InMemoryRateLimiter

router = APIRouter(tags=["feedback"])
logger = logging.getLogger(__name__)

# Limit to 20 feedback submissions per minute per IP.
feedback_limiter = InMemoryRateLimiter(requests_limit=20, window_seconds=60)

# Maps the thumbs value to a numeric Langfuse score.
_VALUE_MAP = {"up": 1.0, "down": 0.0}


@router.post("/feedback")
async def submit_feedback(request: Request, payload: FeedbackRequest) -> dict[str, str]:
    if not obs.langfuse_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feedback is not available",
        )

    client_ip = request.client.host if (request.client and request.client.host) else "unknown"
    if feedback_limiter.is_rate_limited(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )

    recorded = obs.score_feedback(
        trace_id=payload.trace_id,
        value=_VALUE_MAP[payload.value],
        comment=payload.comment,
    )
    if not recorded:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to record feedback",
        )

    return {"status": "ok"}
