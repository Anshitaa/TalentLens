import os
from llm.providers.base import LLMProvider

DEFAULT_MODEL = "gemini-flash-latest"


class GeminiProvider(LLMProvider):
    """LLM provider backed by Google Gemini 1.5 Flash (free tier)."""

    def __init__(self, model: str = DEFAULT_MODEL):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY environment variable is not set. "
                "Get a free key at aistudio.google.com, then:\n"
                "  export GEMINI_API_KEY=AIza..."
            )
        import google.generativeai as genai  # lazy import
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model)

    def name(self) -> str:
        return "gemini-flash-latest"

    def complete(self, messages: list[dict], **kwargs) -> str:
        """Send messages to Gemini and return the text reply."""
        # Gemini uses a single prompt string; concatenate system + user messages
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"[System]: {content}")
            elif role == "assistant":
                parts.append(f"[Assistant]: {content}")
            else:
                parts.append(content)

        prompt = "\n\n".join(parts)
        response = self._model.generate_content(prompt)
        return response.text
