import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models import ChatMessage, ChatRequest, Source
from app.rag.cache import query_cache
from app.rag.guardrails import OUT_OF_SCOPE_RESPONSE, is_portfolio_question
from app.rag.llm import embed_text, generate_answer, generate_answer_stream
from app.rag.prompts import ANSWER_SYSTEM_PROMPT, CONDENSE_SYSTEM_PROMPT
from app.rag.retrieval import RetrievedChunk, search_chunks

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)

NO_CONTEXT_RESPONSE = (
    "I don't have enough information in Siva's portfolio knowledge base to answer that."
)
ERROR_RESPONSE = (
    "Something went wrong while searching Siva's portfolio. Please try again."
)


async def _condense_question(question: str, history: list[ChatMessage]) -> str:
    if not history:
        return question

    history_str = ""
    for msg in history:
        role_name = "User" if msg.role == "user" else "Assistant"
        history_str += f"{role_name}: {msg.content}\n"

    prompt = f"""Chat History:
{history_str}
Latest Question: {question}

Formulate a standalone question that captures the user's intent without referring to the conversation history. If the question is already a standalone question, return it exactly as is. Do NOT answer the question."""

    messages = [
        {"role": "system", "content": CONDENSE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    try:
        condensed_str = await generate_answer(messages)
        condensed_str = condensed_str.strip()
        logger.info(f"Condensed question: '{question}' -> '{condensed_str}'")
        return condensed_str
    except Exception:
        logger.exception("Failed to condense question, falling back to raw question")
        return question


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


def _build_messages(
    question: str, chunks: list[RetrievedChunk], history: list[ChatMessage]
) -> list[dict[str, str]]:
    context = _build_context(chunks)
    
    messages = [{"role": "system", "content": ANSWER_SYSTEM_PROMPT}]
    
    # Append history
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    user_prompt = f"""Portfolio context:

{context}

User question:
{question}

Answer using only the portfolio context above. Include only facts supported by the context."""

    messages.append({"role": "user", "content": user_prompt})
    return messages


def _sources_from_chunks(chunks: list[RetrievedChunk]) -> list[Source]:
    return [
        Source(
            title=chunk.title,
            snippet=chunk.snippet,
        )
        for chunk in chunks
    ]


@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    question = request.message.strip()
    history = request.history

    async def event_generator():
        # Check cache
        cache_key = f"{question}|||{json.dumps([h.dict() if hasattr(h, 'dict') else h.model_dump() for h in history])}"
        cached = query_cache.get(cache_key)
        if cached is not None:
            logger.info("Cache hit for query")
            yield json.dumps({"type": "sources", "sources": cached["sources"]}) + "\n"
            yield json.dumps({"type": "token", "content": cached["answer"]}) + "\n"
            return

        try:
            # 1. Condense the question based on context history
            condensed_question = await _condense_question(question, history)
        except Exception:
            logger.exception("Failed to condense question")
            condensed_question = question

        # 2. Run guardrails on the condensed standalone question
        if not is_portfolio_question(condensed_question):
            yield json.dumps({"type": "token", "content": OUT_OF_SCOPE_RESPONSE}) + "\n"
            yield json.dumps({"type": "sources", "sources": []}) + "\n"
            return

        try:
            # 3. Search database using the condensed question
            query_embedding = await embed_text(condensed_question)
            chunks = await search_chunks(query_embedding)

            if not chunks:
                yield json.dumps({"type": "token", "content": NO_CONTEXT_RESPONSE}) + "\n"
                yield json.dumps({"type": "sources", "sources": []}) + "\n"
                return

            # Yield sources list immediately
            sources_payload = _sources_from_chunks(chunks)
            sources_list = [{"title": s.title, "snippet": s.snippet} for s in sources_payload]
            yield json.dumps({"type": "sources", "sources": sources_list}) + "\n"

            # 4. Generate answer using raw question + context + history
            answer_messages = _build_messages(question, chunks, history)
            accumulated_answer = ""
            async for token in generate_answer_stream(answer_messages):
                accumulated_answer += token
                yield json.dumps({"type": "token", "content": token}) + "\n"

            # Cache the response
            if accumulated_answer.strip():
                query_cache.set(cache_key, {"sources": sources_list, "answer": accumulated_answer})
        except Exception:
            logger.exception("Chat request failed during streaming")
            yield json.dumps({"type": "error", "content": ERROR_RESPONSE}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")
