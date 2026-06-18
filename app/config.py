from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    litellm_embedding_model: str = Field(
        default="gemini/gemini-embedding-001",
        alias="LITELLM_EMBEDDING_MODEL",
    )
    litellm_chat_model: str = Field(
        default="gemini/gemini-2.5-flash",
        alias="LITELLM_CHAT_MODEL",
    )
    neo4j_uri: str = Field(default="", alias="NEO4J_URI")
    neo4j_username: str = Field(default="neo4j", alias="NEO4J_USERNAME")
    neo4j_password: str = Field(default="", alias="NEO4J_PASSWORD")
    rag_top_k: int = Field(default=5, alias="RAG_TOP_K")
    rag_min_score: float = Field(default=0.72, alias="RAG_MIN_SCORE")
    frontend_origin: str = Field(default="http://localhost:3000", alias="FRONTEND_ORIGIN")

    class Config:
        env_file = ".env"
        populate_by_name = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
