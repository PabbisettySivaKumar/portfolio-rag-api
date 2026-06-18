from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)


class Source(BaseModel):
    title: str
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
