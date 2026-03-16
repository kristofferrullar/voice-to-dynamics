from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class RecognisedUtterance:
    raw_text: str
    cleaned_text: str
    confidence: float
    language: str


class STTProvider(ABC):
    """Abstract base for speech-to-text providers.

    Implement this to add a new STT backend (e.g. Whisper).
    Register the implementation in src/providers/factory.py and
    add the provider key to config/pipeline.yaml.
    """

    @abstractmethod
    async def start_session(self) -> None:
        """Start continuous recognition."""

    @abstractmethod
    async def stop_session(self) -> None:
        """Stop recognition and release resources."""

    @abstractmethod
    def utterance_stream(self) -> AsyncIterator[RecognisedUtterance]:
        """Yield completed utterances as they are recognised."""
