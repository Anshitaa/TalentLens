import os

from llm.providers.base import LLMProvider

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class AnthropicProvider(LLMProvider):
    """LLM provider backed by Anthropic's claude-haiku model."""

    def __init__(self, model: str = DEFAULT_MODEL):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Export it before using AnthropicProvider:\n"
                "  export ANTHROPIC_API_KEY=sk-ant-..."
            )
        import anthropic  # lazy import — only needed when this provider is used
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, messages: list[dict], **kwargs) -> str:
        """
        Send messages to Claude and return the text reply.

        Separates an optional leading system message from the user/assistant turns,
        as the Anthropic SDK passes system prompts separately.
        """
        system_prompt = None
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                chat_messages.append({"role": msg["role"], "content": msg["content"]})

        create_kwargs = {
            "model": self._model,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "messages": chat_messages,
        }
        if system_prompt:
            create_kwargs["system"] = system_prompt

        response = self._client.messages.create(**create_kwargs)
        return response.content[0].text

    def name(self) -> str:
        return f"anthropic/{self._model}"
