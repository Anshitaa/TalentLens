from llm.providers.base import LLMProvider


def get_provider(tier: str = "gemini") -> LLMProvider:
    """
    Return the appropriate LLM provider.

    tier options:
      "gemini"    → GeminiProvider (gemini-1.5-flash, free tier)
      "anthropic" → AnthropicProvider (claude-haiku-4-5-20251001)
      "openai"    → OpenAIProvider (gpt-4o-mini)
      "local"     → OllamaProvider (llama3, no key needed)
    """
    if tier == "gemini":
        from llm.providers.gemini_provider import GeminiProvider
        return GeminiProvider()
    elif tier == "openai":
        from llm.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()
    elif tier == "local":
        from llm.providers.ollama_provider import OllamaProvider
        return OllamaProvider()
    else:  # anthropic
        from llm.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
