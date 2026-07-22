from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    session_id: str | None = Field(default=None)


class FeedbackRequest(BaseModel):
    trace_id: str = Field(min_length=1)
    value: Literal["up", "down"]
    comment: str | None = Field(default=None, max_length=2000)


class Source(BaseModel):
    title: str
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
