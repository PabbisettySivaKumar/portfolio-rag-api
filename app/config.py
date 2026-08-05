from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    litellm_embedding_model: str = Field(
        default="gemini/gemini-embedding-001",
        alias="LITELLM_EMBEDDING_MODEL",
    )
    litellm_chat_model: str = Field(
        default="gemini/gemini-3.1-flash-lite",
        alias="LITELLM_CHAT_MODEL",
    )
    litellm_fallback_model: str = Field(
        default="gemini/gemini-2.5-flash",
        alias="LITELLM_FALLBACK_MODEL",
    )
    neo4j_uri: str = Field(default="", alias="NEO4J_URI")
    neo4j_username: str = Field(default="neo4j", alias="NEO4J_USERNAME")
    neo4j_password: str = Field(default="", alias="NEO4J_PASSWORD")
    keepalive_token: str = Field(default="", alias="KEEPALIVE_TOKEN")
    langfuse_enabled: bool = Field(default=False, alias="LANGFUSE_ENABLED")
    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_HOST", "LANGFUSE_BASE_URL"),
    )
    rag_top_k: int = Field(default=10, alias="RAG_TOP_K")
    # Tuned via evals/run_eval.py --sweep: 0.80 trims low-relevance chunks with
    # no recall/precision loss on the eval set (100% recall holds up to ~0.83).
    rag_min_score: float = Field(default=0.80, alias="RAG_MIN_SCORE")
    # Single origin or a comma-separated list (e.g. apex + www domain), used as
    # the CORS allow-list. See frontend_origins for the parsed value.
    frontend_origin: str = Field(default="http://localhost:3000", alias="FRONTEND_ORIGIN")

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    @field_validator("keepalive_token")
    @classmethod
    def validate_keepalive_token(cls, v: str) -> str:
        if v and len(v) < 32:
            raise ValueError("KEEPALIVE_TOKEN must be at least 32 characters long for security.")
        return v

    class Config:
        env_file = ".env"
        populate_by_name = True
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
