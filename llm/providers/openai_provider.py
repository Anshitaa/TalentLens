import os

from llm.providers.base import LLMProvider

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(LLMProvider):
    """LLM provider backed by OpenAI's gpt-4o-mini model."""

    def __init__(self, model: str = DEFAULT_MODEL):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY environment variable is not set. "
                "Export it before using OpenAIProvider:\n"
                "  export OPENAI_API_KEY=sk-..."
            )
        import openai  # lazy import
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    def complete(self, messages: list[dict], **kwargs) -> str:
        """Send messages to OpenAI and return the assistant reply text."""
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=kwargs.get("max_tokens", 1024),
            temperature=kwargs.get("temperature", 0.2),
        )
        return response.choices[0].message.content

    def name(self) -> str:
        return f"openai/{self._model}"
