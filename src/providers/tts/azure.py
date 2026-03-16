import azure.cognitiveservices.speech as speechsdk

from config.settings import get_settings
from src.providers.tts.base import TTSProvider


class AzureTTSProvider(TTSProvider):
    """Azure Cognitive Services Text-to-Speech."""

    def __init__(self, voice: str = "sv-SE-MattiasNeural") -> None:
        settings = get_settings()
        self._speech_config = speechsdk.SpeechConfig(
            subscription=settings.azure_speech_key,
            region=settings.azure_speech_region,
        )
        self._speech_config.speech_synthesis_voice_name = voice
        self._synthesizer = speechsdk.SpeechSynthesizer(speech_config=self._speech_config)

    async def speak(self, text: str) -> None:
        if not text.strip():
            return
        result = self._synthesizer.speak_text_async(text).get()
        if result.reason == speechsdk.ResultReason.Canceled:
            details = speechsdk.SpeechSynthesisCancellationDetails(result)
            raise RuntimeError(f"Azure TTS cancelled: {details.reason} — {details.error_details}")
