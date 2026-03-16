from abc import ABC, abstractmethod


class ConversationHost(ABC):
    """Abstract base for the conversational host provider.

    The host gives a brief spoken acknowledgement while the agent
    processes the full request in parallel.

    Implement this to add a new host backend (e.g. Claude Haiku).
    Register in src/providers/factory.py and config/pipeline.yaml.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection / warm up the provider."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection and release resources."""

    @abstractmethod
    async def respond_audio(self, text: str) -> None:
        """Generate and play a brief spoken acknowledgement for the utterance."""
