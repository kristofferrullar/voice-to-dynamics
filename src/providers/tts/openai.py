"""OpenAI TTS provider stub.

Implement using openai.audio.speech.create.
Set ``tts.provider: openai`` in config/pipeline.yaml to activate.
"""
from src.providers.tts.base import TTSProvider


class OpenAITTSProvider(TTSProvider):
    """OpenAI text-to-speech (stub — not yet implemented)."""

    async def speak(self, text: str) -> None:
        raise NotImplementedError("OpenAITTSProvider is not yet implemented")
