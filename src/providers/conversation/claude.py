"""Claude Haiku fallback conversation host.

Generates a short text acknowledgement and speaks it via the TTS provider.
Set ``conversation_host.provider: claude`` in config/pipeline.yaml to activate.
"""
import anthropic

from config.settings import get_settings
from src.providers.conversation.base import ConversationHost

_SYSTEM = (
    "You are a voice assistant. Reply with exactly one short sentence that acknowledges "
    "what the user asked. Do not perform the action yourself. "
    "If the user speaks Swedish, reply in Swedish instead."
)


class ClaudeConversationHost(ConversationHost):
    """Conversation host using Claude Haiku for text acknowledgement."""

    def __init__(self, tts_speak_fn, system_prompt: str = _SYSTEM) -> None:  # type: ignore[type-arg]
        self._tts_speak = tts_speak_fn
        self._system = system_prompt
        self._client: anthropic.AsyncAnthropic | None = None

    async def connect(self) -> None:
        settings = get_settings()
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def disconnect(self) -> None:
        self._client = None

    async def respond_audio(self, text: str) -> None:
        if not self._client:
            await self.connect()
        response = await self._client.messages.create(  # type: ignore[union-attr]
            model="claude-haiku-4-5",
            max_tokens=80,
            system=self._system,
            messages=[{"role": "user", "content": text}],
        )
        reply = response.content[0].text if response.content else ""
        if reply:
            await self._tts_speak(reply)
