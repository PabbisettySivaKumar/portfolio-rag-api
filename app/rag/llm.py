import os

from litellm import completion, embedding

from app.config import settings


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
    response = completion(
        model=settings.litellm_chat_model,
        messages=messages,
    )
    message = response.choices[0].message
    if isinstance(message, dict):
        return message.get("content", "")
    return message.content or ""
