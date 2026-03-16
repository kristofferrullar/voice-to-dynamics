from abc import ABC, abstractmethod


class TTSProvider(ABC):
    """Abstract base for text-to-speech providers.

    Implement this to add a new TTS backend (e.g. OpenAI TTS).
    Register the implementation in src/providers/factory.py and
    add the provider key to config/pipeline.yaml.
    """

    @abstractmethod
    async def speak(self, text: str) -> None:
        """Synthesise text and play audio to the default speaker."""
