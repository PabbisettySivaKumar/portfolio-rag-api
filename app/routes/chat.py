import logging

from fastapi import APIRouter

from app.models import ChatRequest, ChatResponse, Source
from app.rag.guardrails import OUT_OF_SCOPE_RESPONSE, is_portfolio_question
from app.rag.llm import embed_text, generate_answer
from app.rag.prompts import ANSWER_SYSTEM_PROMPT
from app.rag.retrieval import RetrievedChunk, search_chunks

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)

NO_CONTEXT_RESPONSE = (
    "I don't have enough information in Siva's portfolio knowledge base to answer that."
)
ERROR_RESPONSE = (
    "Something went wrong while searching Siva's portfolio. Please try again."
)


def _build_context(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for index, chunk in enumerate(chunks, start=1):
        parts.append(
            "\n".join(
                [
                    f"[Source {index}]",
                    f"Title: {chunk.title}",
                    f"File: {chunk.source}",
                    f"Section: {chunk.section}",
                    f"Score: {chunk.score:.4f}",
                    "Content:",
                    chunk.content,
                ]
            )
        )
    return "\n\n---\n\n".join(parts)


def _build_messages(question: str, chunks: list[RetrievedChunk]) -> list[dict[str, str]]:
    context = _build_context(chunks)
    user_prompt = f"""Portfolio context:

{context}

User question:
{question}

Answer using only the portfolio context above. Include only facts supported by the context."""

    return [
        {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _sources_from_chunks(chunks: list[RetrievedChunk]) -> list[Source]:
    return [
        Source(
            title=chunk.title,
            snippet=chunk.snippet,
        )
        for chunk in chunks
    ]


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    question = request.message.strip()

    if not is_portfolio_question(question):
        return ChatResponse(answer=OUT_OF_SCOPE_RESPONSE, sources=[])

    try:
        query_embedding = embed_text(question)
        chunks = search_chunks(query_embedding)

        if not chunks:
            return ChatResponse(answer=NO_CONTEXT_RESPONSE, sources=[])

        answer = generate_answer(_build_messages(question, chunks))
        return ChatResponse(answer=answer, sources=_sources_from_chunks(chunks))
    except Exception:
        logger.exception("Chat request failed")
        return ChatResponse(answer=ERROR_RESPONSE, sources=[])
