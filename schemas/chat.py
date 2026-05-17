from typing import List, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    model: str = Field(
        "claude-sonnet-4-5",
        description="Anthropic model id (e.g. claude-sonnet-4-5, claude-haiku-4-5).",
    )
    system_prompt: str = Field(
        "You are a helpful assistant.",
        description="System prompt for the conversation.",
    )
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(1000, ge=1)
    messages: List[ChatMessage] = Field(
        ..., description="Conversation history excluding the system prompt."
    )


class ChatError(BaseModel):
    detail: str
