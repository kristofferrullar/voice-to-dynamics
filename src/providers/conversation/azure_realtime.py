"""Azure OpenAI Real-time API conversation host.

Connects via WebSocket, sends user text, streams back spoken audio.
Gives the tightest acknowledgement latency (~300 ms).

Protocol reference:
  https://learn.microsoft.com/azure/ai-services/openai/realtime-audio-reference
"""
import asyncio
import base64
import json
import logging

import sounddevice as sd  # type: ignore[import-untyped]
import numpy as np
import websockets
from websockets.asyncio.client import ClientConnection

from config.settings import get_settings
from src.providers.conversation.base import ConversationHost

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 24000
_CHANNELS = 1


class AzureRealtimeConversationHost(ConversationHost):
    """Conversational host backed by Azure OpenAI Real-time API."""

    def __init__(self, system_prompt: str) -> None:
        self._system_prompt = system_prompt
        self._ws: ClientConnection | None = None

    async def connect(self) -> None:
        settings = get_settings()
        endpoint = settings.azure_openai_endpoint.rstrip("/")
        deployment = settings.azure_openai_realtime_deployment
        api_key = settings.azure_openai_api_key

        url = (
            f"{endpoint.replace('https://', 'wss://')}"
            f"/openai/realtime"
            f"?api-version=2024-10-01-preview"
            f"&deployment={deployment}"
        )
        self._ws = await websockets.connect(
            url,
            additional_headers={"api-key": api_key},
        )
        # Configure session: text input, audio output, Swedish voice
        await self._send(
            {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": self._system_prompt,
                    "voice": "alloy",
                    "output_audio_format": "pcm16",
                    "turn_detection": None,
                },
            }
        )
        logger.info("Azure Real-time session connected")

    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def respond_audio(self, text: str) -> None:
        if not self._ws:
            await self.connect()

        # Send user message and request a response
        await self._send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                },
            }
        )
        await self._send({"type": "response.create"})

        # Collect audio deltas until response is complete
        audio_chunks: list[bytes] = []
        async for raw in self._ws:  # type: ignore[union-attr]
            event = json.loads(raw)
            event_type = event.get("type", "")
            if event_type == "response.audio.delta":
                chunk = base64.b64decode(event["delta"])
                audio_chunks.append(chunk)
            elif event_type == "response.done":
                break
            elif event_type == "error":
                logger.error("Real-time API error: %s", event)
                break

        if audio_chunks:
            _play_pcm16(b"".join(audio_chunks))

    async def _send(self, payload: dict) -> None:  # type: ignore[type-arg]
        if self._ws:
            await self._ws.send(json.dumps(payload))


def _play_pcm16(data: bytes) -> None:
    """Play raw PCM16 audio through the default speaker (blocking)."""
    audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
    sd.play(audio, samplerate=_SAMPLE_RATE)
    sd.wait()
