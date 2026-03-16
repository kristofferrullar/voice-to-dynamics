"""Whisper STT provider stub.

Implement using openai.audio.transcriptions or a local whisper model.
Set ``stt.provider: whisper`` in config/pipeline.yaml to activate.
"""
from collections.abc import AsyncIterator

from src.providers.stt.base import RecognisedUtterance, STTProvider


class WhisperSTTProvider(STTProvider):
    """OpenAI Whisper speech-to-text (stub — not yet implemented)."""

    async def start_session(self) -> None:
        raise NotImplementedError("WhisperSTTProvider is not yet implemented")

    async def stop_session(self) -> None:
        raise NotImplementedError("WhisperSTTProvider is not yet implemented")

    async def utterance_stream(self) -> AsyncIterator[RecognisedUtterance]:  # type: ignore[override]
        raise NotImplementedError("WhisperSTTProvider is not yet implemented")
        yield  # make this an async generator
