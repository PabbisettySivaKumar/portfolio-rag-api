"""Langfuse observability wiring for the RAG pipeline.

Two integration levels are set up here:

* Level A - LiteLLM callback: every LiteLLM completion/embedding call is
  reported to Langfuse automatically (model, prompt, response, tokens, cost,
  latency, errors).
* Level B - manual pipeline tracing: each ``/chat`` request is grouped into a
  single Langfuse trace with child spans (cache -> condense -> guardrail ->
  embed -> retrieval -> generate). The Level A generations are nested under the
  same trace by passing ``existing_trace_id`` in the LiteLLM ``metadata`` kwarg.

Everything degrades to a no-op when Langfuse is disabled or misconfigured, so
the app runs unchanged without observability.
"""

import logging
import os
import re
from typing import Any

from app.config import settings
from app.rag.prompts import LANGFUSE_PROMPTS

logger = logging.getLogger(__name__)

_langfuse_client = None

# How long a fetched prompt is reused before Langfuse is checked again. Edits in
# the Langfuse UI take at most this long to propagate to a running server.
_PROMPT_CACHE_TTL_SECONDS = 300

# PII redaction applied to everything shipped to Langfuse.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Matches +country-code numbers (e.g. +91-7702999095) or bare 10+ digit runs,
# without catching short "2018 - 2020" style ranges.
_PHONE_RE = re.compile(r"\+\d[\d\s\-()]{7,}\d|\b\d{10,}\b")


def _redact(text: str) -> str:
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _PHONE_RE.sub("[redacted-phone]", text)
    return text


def mask_pii(data: Any = None, **kwargs: Any) -> Any:
    """Recursively redact emails and phone numbers from any trace payload.

    Used as the Langfuse client ``mask`` hook, so it must accept strings,
    dicts, lists, and nested combinations, and never raise.
    """
    try:
        if isinstance(data, str):
            return _redact(data)
        if isinstance(data, dict):
            return {key: mask_pii(data=value) for key, value in data.items()}
        if isinstance(data, (list, tuple)):
            return [mask_pii(data=item) for item in data]
        return data
    except Exception:
        logger.exception("PII masking failed; dropping value")
        return "[redacted]"


def langfuse_enabled() -> bool:
    return bool(
        settings.langfuse_enabled
        and settings.langfuse_public_key
        and settings.langfuse_secret_key
    )


def init_langfuse() -> None:
    """Configure LiteLLM -> Langfuse callbacks and the Langfuse SDK client.

    Safe to call once at startup. No-ops when Langfuse is not configured.
    """
    global _langfuse_client

    if not langfuse_enabled():
        logger.info("Langfuse disabled or not configured; skipping observability init")
        return

    # Both the LiteLLM callback and the Langfuse SDK read credentials from env.
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
    os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
    os.environ["LANGFUSE_HOST"] = settings.langfuse_host

    # Level A: route every LiteLLM call (success and failure) to Langfuse.
    # LiteLLM builds its own Langfuse client, so our mask below can't reach it;
    # redact message content on that path instead (token/cost/latency are kept).
    try:
        import litellm

        litellm.turn_off_message_logging = True
        if "langfuse" not in litellm.success_callback:
            litellm.success_callback.append("langfuse")
        if "langfuse" not in litellm.failure_callback:
            litellm.failure_callback.append("langfuse")
    except Exception:
        logger.exception("Failed to register LiteLLM Langfuse callbacks")

    # Level B: SDK client for manual pipeline traces/spans. The mask hook redacts
    # PII from all trace/span inputs and outputs before they are sent.
    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(mask=mask_pii)
        logger.info("Langfuse observability initialized (host=%s)", settings.langfuse_host)
    except Exception:
        logger.exception("Failed to initialize Langfuse SDK client")
        _langfuse_client = None


def get_client():
    """Return the initialized Langfuse SDK client, or None when disabled.

    Exposed for offline tooling (e.g. the dataset eval runner) that needs the
    raw client for datasets/scores rather than the request-path trace helpers.
    """
    return _langfuse_client


def flush_langfuse() -> None:
    """Flush any buffered events. Call on shutdown so nothing is lost."""
    if _langfuse_client is None:
        return
    try:
        _langfuse_client.flush()
    except Exception:
        logger.exception("Failed to flush Langfuse")


def get_prompt(name: str, cache_ttl_seconds: int = _PROMPT_CACHE_TTL_SECONDS) -> str:
    """Return the text of a Langfuse-managed prompt, falling back to the bundled
    default in ``LANGFUSE_PROMPTS``.

    Returns the local default verbatim when Langfuse is disabled, when the prompt
    has not been seeded yet, or when the fetch fails, so behaviour is identical
    without observability configured. Results are cached by the Langfuse SDK for
    ``cache_ttl_seconds`` to avoid a network call on every request.
    """
    fallback = LANGFUSE_PROMPTS[name]
    if _langfuse_client is None:
        return fallback
    try:
        prompt = _langfuse_client.get_prompt(
            name,
            fallback=fallback,
            label="production",
            cache_ttl_seconds=cache_ttl_seconds,
        )
        return prompt.prompt
    except Exception:
        logger.exception("Langfuse get_prompt failed for %s; using bundled default", name)
        return fallback


def seed_prompts(*, force: bool = False) -> dict:
    """Create the managed prompts in Langfuse from the bundled defaults.

    Idempotent: existing prompts are skipped unless ``force`` creates a new
    version. Intended to be run once from scripts/seed_langfuse_prompts.py, not
    on every startup (each create call would otherwise add a version).
    """
    if _langfuse_client is None:
        raise RuntimeError("Langfuse is not enabled/configured; cannot seed prompts")

    created, skipped = [], []
    for name, text in LANGFUSE_PROMPTS.items():
        if not force:
            try:
                # get_prompt without a fallback raises when the prompt is absent.
                _langfuse_client.get_prompt(name, cache_ttl_seconds=0)
                skipped.append(name)
                continue
            except Exception:
                pass
        _langfuse_client.create_prompt(
            name=name,
            prompt=text,
            labels=["production"],
            type="text",
        )
        created.append(name)
    _langfuse_client.flush()
    return {"created": created, "skipped": skipped}


def start_trace(name: str, user_input: str, session_id: str | None = None):
    """Create a request-level trace, or return None when disabled/failed."""
    if _langfuse_client is None:
        return None
    try:
        return _langfuse_client.trace(
            name=name,
            input=user_input,
            session_id=session_id,
            tags=["rag", "portfolio"],
        )
    except Exception:
        logger.exception("Langfuse start_trace failed")
        return None


def start_span(trace, name: str, span_input=None, metadata: dict | None = None):
    """Open a child span under ``trace``. Returns None when tracing is off."""
    if trace is None:
        return None
    try:
        return trace.span(name=name, input=span_input, metadata=metadata)
    except Exception:
        logger.exception("Langfuse start_span failed for %s", name)
        return None


def end_span(span, output=None, metadata: dict | None = None) -> None:
    if span is None:
        return
    try:
        span.end(output=output, metadata=metadata)
    except Exception:
        logger.exception("Langfuse end_span failed")


def update_trace(trace, output=None, metadata: dict | None = None) -> None:
    if trace is None:
        return
    try:
        trace.update(output=output, metadata=metadata)
    except Exception:
        logger.exception("Langfuse update_trace failed")


def score_feedback(
    trace_id: str, value: float, comment: str | None = None
) -> bool:
    """Attach a user-feedback score to an existing trace. Returns False when
    tracing is off or the call fails.
    """
    if _langfuse_client is None:
        return False
    try:
        _langfuse_client.score(
            trace_id=trace_id,
            name="user-feedback",
            value=value,
            comment=comment,
        )
        return True
    except Exception:
        logger.exception("Langfuse score_feedback failed")
        return False


def llm_metadata(
    trace, generation_name: str, session_id: str | None = None
) -> dict | None:
    """Build the LiteLLM ``metadata`` payload that nests a generation under
    ``trace`` in Langfuse. Returns None when tracing is off so callers can pass
    it through unchanged.
    """
    if trace is None:
        return None
    metadata: dict = {
        "existing_trace_id": trace.id,
        "generation_name": generation_name,
    }
    if session_id:
        metadata["session_id"] = session_id
    return metadata
