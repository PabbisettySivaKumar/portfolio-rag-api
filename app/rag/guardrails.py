OUT_OF_SCOPE_RESPONSE = (
    "I can only answer questions about Siva Kumar's experience, projects, "
    "skills, education, contact, and availability."
)


def is_portfolio_question(message: str) -> bool:
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
    }
    normalized = message.lower()
    return any(term in normalized for term in allowed_terms)
