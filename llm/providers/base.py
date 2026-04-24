from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[dict], **kwargs) -> str:
        """
        Send a list of chat messages and return the assistant reply as a string.

        messages format: [{"role": "user"|"assistant"|"system", "content": "..."}]
        """
        ...

    @abstractmethod
    def name(self) -> str:
        """Return a human-readable identifier for this provider/model."""
        ...
