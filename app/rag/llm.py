import logging
import os

from litellm import completion, embedding

from app.config import settings

logger = logging.getLogger(__name__)


def _ensure_gemini_key() -> None:
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key


def embed_text(text: str) -> list[float]:
    _ensure_gemini_key()
    response = embedding(
        model=settings.litellm_embedding_model,
        input=[text],
    )
    item = response.data[0]
    if isinstance(item, dict):
        return item["embedding"]
    return item.embedding


def generate_answer(messages: list[dict[str, str]]) -> str:
    _ensure_gemini_key()
    try:
        response = completion(
            model=settings.litellm_chat_model,
            messages=messages,
        )
        message = response.choices[0].message
        if isinstance(message, dict):
            return message.get("content", "")
        return message.content or ""
    except Exception as e:
        logger.warning(
            f"Primary model {settings.litellm_chat_model} failed: {e}. "
            f"Falling back to {settings.litellm_fallback_model}."
        )
        response = completion(
            model=settings.litellm_fallback_model,
            messages=messages,
        )
        message = response.choices[0].message
        if isinstance(message, dict):
            return message.get("content", "")
        return message.content or ""


def generate_answer_stream(messages: list[dict[str, str]]):
    _ensure_gemini_key()
    try:
        response = completion(
            model=settings.litellm_chat_model,
            messages=messages,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta
            if isinstance(delta, dict):
                content = delta.get("content", "")
            else:
                content = getattr(delta, "content", "") or ""
            if content:
                yield content
    except Exception as e:
        logger.warning(
            f"Primary model {settings.litellm_chat_model} failed: {e}. "
            f"Falling back to stream on {settings.litellm_fallback_model}."
        )
        response = completion(
            model=settings.litellm_fallback_model,
            messages=messages,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta
            if isinstance(delta, dict):
                content = delta.get("content", "")
            else:
                content = getattr(delta, "content", "") or ""
            if content:
                yield content
