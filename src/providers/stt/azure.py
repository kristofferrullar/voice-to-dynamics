import asyncio
from collections.abc import AsyncIterator
from typing import Any

import azure.cognitiveservices.speech as speechsdk

from config.settings import get_settings
from src.stt.preprocessor import SwedishPreprocessor
from src.providers.stt.base import RecognisedUtterance, STTProvider


class AzureSTTProvider(STTProvider):
    """Azure Cognitive Services Speech-to-Text (continuous recognition)."""

    def __init__(self, language: str = "sv-SE", filler_word_removal: bool = True) -> None:
        settings = get_settings()
        self._speech_config = speechsdk.SpeechConfig(
            subscription=settings.azure_speech_key,
            region=settings.azure_speech_region,
        )
        self._speech_config.speech_recognition_language = language
        self._language = language
        self._preprocessor = SwedishPreprocessor() if filler_word_removal else None
        self._recognizer: speechsdk.SpeechRecognizer | None = None
        self._queue: asyncio.Queue[RecognisedUtterance] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start_session(self) -> None:
        self._loop = asyncio.get_running_loop()
        audio_config = speechsdk.AudioConfig(use_default_microphone=True)
        self._recognizer = speechsdk.SpeechRecognizer(
            speech_config=self._speech_config,
            audio_config=audio_config,
        )
        self._recognizer.recognized.connect(self._on_recognised)
        await asyncio.get_running_loop().run_in_executor(
            None, self._recognizer.start_continuous_recognition
        )

    async def stop_session(self) -> None:
        if self._recognizer:
            await asyncio.get_running_loop().run_in_executor(
                None, self._recognizer.stop_continuous_recognition
            )

    async def utterance_stream(self) -> AsyncIterator[RecognisedUtterance]:  # type: ignore[override]
        while True:
            utterance = await self._queue.get()
            yield utterance

    def _on_recognised(self, evt: Any) -> None:
        if evt.result.reason != speechsdk.ResultReason.RecognizedSpeech:
            return
        raw = evt.result.text.strip()
        if not raw:
            return
        cleaned = self._preprocessor.clean(raw) if self._preprocessor else raw
        if not cleaned:
            return
        utterance = RecognisedUtterance(
            raw_text=raw,
            cleaned_text=cleaned,
            confidence=1.0,  # Azure SDK does not expose word-level confidence directly
            language=self._language,
        )
        if self._loop:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, utterance)
