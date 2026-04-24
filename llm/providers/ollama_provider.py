import json

import requests

from llm.providers.base import LLMProvider

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3"


class OllamaProvider(LLMProvider):
    """
    Local LLM provider via Ollama.
    No API key required — runs against a locally running Ollama server.
    Start the model with: ollama run llama3
    """

    def __init__(self, model: str = DEFAULT_MODEL, base_url: str = OLLAMA_BASE_URL):
        self._model = model
        self._base_url = base_url.rstrip("/")

    def complete(self, messages: list[dict], **kwargs) -> str:
        """
        POST to Ollama's /api/chat endpoint and return the assistant reply.
        Falls back to a descriptive error string if Ollama is not running.
        """
        url = f"{self._base_url}/api/chat"
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.2),
                "num_predict": kwargs.get("max_tokens", 1024),
            },
        }

        try:
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
        except requests.exceptions.ConnectionError:
            return (
                "[Ollama unavailable — start with: ollama run llama3]"
            )
        except requests.exceptions.Timeout:
            return "[Ollama request timed out — model may still be loading]"
        except Exception as exc:
            return f"[Ollama error: {exc}]"

    def name(self) -> str:
        return f"ollama/{self._model}"
