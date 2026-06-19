import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models import ChatMessage, ChatRequest, Source
from app.rag.guardrails import OUT_OF_SCOPE_RESPONSE, is_portfolio_question
from app.rag.llm import embed_text, generate_answer_stream
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


def _condense_question(question: str, history: list[ChatMessage]) -> str:
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
        condensed = generate_answer_stream(messages)
        condensed_str = "".join(list(condensed)).strip()
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
def chat(request: ChatRequest) -> StreamingResponse:
    question = request.message.strip()
    history = request.history

    def event_generator():
        try:
            # 1. Condense the question based on context history
            condensed_question = _condense_question(question, history)
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
            query_embedding = embed_text(condensed_question)
            chunks = search_chunks(query_embedding)

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
            for token in generate_answer_stream(answer_messages):
                yield json.dumps({"type": "token", "content": token}) + "\n"
        except Exception:
            logger.exception("Chat request failed during streaming")
            yield json.dumps({"type": "error", "content": ERROR_RESPONSE}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")
