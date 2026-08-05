import logging

from app.rag import observability as obs
from app.rag.llm import generate_answer

logger = logging.getLogger(__name__)

OUT_OF_SCOPE_RESPONSE = (
    "I can only answer questions about Siva Kumar's experience, projects, "
    "skills, education, contact, and availability."
)


def _keyword_accept(message: str) -> bool:
    """Fast path: obvious portfolio questions are accepted without an LLM call."""
    allowed_terms = {
        "siva",
        "portfolio",
        "project",
        "projects",
        "skill",
        "skills",
        "experience",
        "education",
        "resume",
        "rag",
        "langchain",
        "langgraph",
        "neo4j",
        "fastapi",
        "ai",
        "engineer",
        "availability",
        "contact",
        "email",
        "phone",
        "mobile",
        "number",
        "github",
        "linkedin",
        "dotkonnekt",
        "mast global",
        "victoria",
        "coursera",
        "certification",
        "certifications",
        "reddit",
        "pipeline",
        "pipelines",
        "analytics",
        "multimodal",
        "text-to-image",
        "intelligent",
        "analysis",
        "csv",
        "nlp",
        "stack",
        "tech",
        "technology",
        "technologies",
        "tool",
        "tools",
        "work",
        "job",
        "jobs",
        "role",
        "roles",
        "position",
        "hire",
        "hiring",
        "recruit",
    }
    normalized = message.lower()
    return any(term in normalized for term in allowed_terms)


async def is_portfolio_question(message: str, metadata: dict | None = None) -> bool:
    """Return True when the question is in scope for the portfolio assistant.

    Keyword matches are accepted immediately. Everything else is handed to an
    LLM scope classifier so natural phrasings ("who are you?", "tell me about
    his background") are handled instead of being hard-rejected by a wordlist.
    The classifier fails open: any error allows the question through, where
    retrieval will fall back to the no-context response if it truly is off topic.
    """
    if _keyword_accept(message):
        return True

    try:
        verdict = await generate_answer(
            [
                {"role": "system", "content": obs.get_prompt("portfolio-scope-classifier")},
                {"role": "user", "content": message},
            ],
            metadata,
        )
        return verdict.strip().upper().startswith("Y")
    except Exception:
        logger.exception("Scope classifier failed; allowing question through")
        return True
