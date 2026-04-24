from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for the /agent/chat endpoint."""

    message: str = Field(description="The user message to send to the agent")
    provider: str = Field(
        default="gemini",
        description="LLM provider to use: 'gemini' (free), 'anthropic', 'openai', or 'local'",
    )


class ChatResponse(BaseModel):
    """Response from the /agent/chat endpoint."""

    response: str = Field(description="The agent's reply text")
    tool_calls_used: list[str] = Field(
        default_factory=list,
        description="Names of any tools the agent invoked to answer the question",
    )
