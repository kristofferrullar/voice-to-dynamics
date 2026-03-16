"""Telegram Bot channel adapter — text AND voice messages.

Two modes:
  - Webhook  (production): Telegram POSTs to /webhook/telegram
  - Polling  (dev/local):  call start_polling() — no public URL needed

Voice flow:
  User sends voice note → download OGG/OPUS → Azure STT → agent → Azure TTS → reply as voice note

Setup (2 minutes, no phone number or approval required):
  1. Open Telegram → search @BotFather → /newbot
  2. Pick a name and username → copy the token
  3. Set TELEGRAM_BOT_TOKEN=<token> in .env
  4. Run 'python -m voice_mcp ui' and start chatting or sending voice notes
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE      = "https://api.telegram.org/bot{token}/{method}"
_FILE_BASE = "https://api.telegram.org/file/bot{token}/{file_path}"


# ── Low-level Telegram API helpers ────────────────────────────────────────────

async def _api(token: str, method: str, **kwargs: Any) -> dict[str, Any]:
    """Call the Telegram Bot API (JSON body) and return the result dict."""
    url = _BASE.format(token=token, method=method)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=kwargs)
    data = resp.json()
    if not data.get("ok"):
        logger.warning("Telegram API error (%s): %s", method, data.get("description"))
    return data


async def send_message(token: str, chat_id: int | str, text: str) -> None:
    """Send a text message to a Telegram chat."""
    await _api(token, "sendMessage", chat_id=chat_id, text=text)


async def send_voice(token: str, chat_id: int | str, ogg_bytes: bytes) -> None:
    """Send an OGG/OPUS audio file as a Telegram voice message."""
    url = _BASE.format(token=token, method="sendVoice")
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url,
            data={"chat_id": str(chat_id)},
            files={"voice": ("voice.ogg", ogg_bytes, "audio/ogg")},
        )
    data = resp.json()
    if not data.get("ok"):
        logger.warning("Telegram sendVoice error: %s", data.get("description"))


async def send_typing(token: str, chat_id: int | str) -> None:
    """Send 'recording audio' action so the user sees the bot is working."""
    await _api(token, "sendChatAction", chat_id=chat_id, action="record_voice")


# ── Voice file download ────────────────────────────────────────────────────────

async def download_voice(token: str, file_id: str) -> bytes:
    """Download a voice message OGG file from Telegram and return raw bytes."""
    # Step 1: resolve file_id → file_path
    info = await _api(token, "getFile", file_id=file_id)
    file_path = info["result"]["file_path"]

    # Step 2: download the actual bytes
    url = _FILE_BASE.format(token=token, file_path=file_path)
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url)
    resp.raise_for_status()
    return resp.content


# ── Azure Speech STT via REST (OGG/OPUS → text) ───────────────────────────────

async def transcribe_ogg(
    audio_bytes: bytes,
    speech_key: str,
    speech_region: str,
    language: str = "en-US",
) -> str:
    """Transcribe OGG/OPUS audio bytes using Azure Cognitive Services Speech REST API.

    Returns the recognised text, or an empty string on failure.
    """
    url = (
        f"https://{speech_region}.stt.speech.microsoft.com"
        f"/speech/recognition/conversation/cognitiveservices/v1"
    )
    headers = {
        "Ocp-Apim-Subscription-Key": speech_key,
        "Content-Type": "audio/ogg; codecs=opus",
    }
    params = {"language": language, "format": "simple"}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, params=params, headers=headers, content=audio_bytes)

    if resp.status_code != 200:
        logger.warning("Azure STT error %s: %s", resp.status_code, resp.text[:200])
        return ""

    data = resp.json()
    status = data.get("RecognitionStatus", "")
    if status != "Success":
        logger.warning("Azure STT status: %s", status)
        return ""

    return data.get("DisplayText", "").strip()


# ── Azure Speech TTS via REST (text → OGG/OPUS bytes) ─────────────────────────

async def synthesize_to_ogg(
    text: str,
    speech_key: str,
    speech_region: str,
    voice: str = "en-US-AriaNeural",
) -> bytes:
    """Synthesize text to OGG/OPUS audio using Azure Cognitive Services TTS REST API.

    Returns raw OGG bytes suitable for Telegram's sendVoice.
    """
    # Step 1: get a short-lived bearer token
    token_url = f"https://{speech_region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            token_url,
            headers={"Ocp-Apim-Subscription-Key": speech_key},
        )
    token_resp.raise_for_status()
    token = token_resp.text

    # Step 2: synthesize
    tts_url = f"https://{speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"
    # Determine xml:lang from voice name (first two segments: en-US, sv-SE, …)
    lang = "-".join(voice.split("-")[:2])
    ssml = (
        f"<speak version='1.0' xml:lang='{lang}'>"
        f"<voice name='{voice}'>{text}</voice>"
        "</speak>"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "ogg-48khz-16bit-mono-opus",
        "User-Agent": "voice-mcp",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(tts_url, headers=headers, content=ssml.encode())

    if resp.status_code != 200:
        logger.warning("Azure TTS error %s: %s", resp.status_code, resp.text[:200])
        raise RuntimeError(f"TTS failed: {resp.status_code}")

    return resp.content


# ── Incoming update parser ─────────────────────────────────────────────────────

def parse_update(update: dict[str, Any]) -> dict[str, Any] | None:
    """Extract message info from a Telegram Update object.

    Returns a dict with keys:
      update_id, chat_id, user, text (may be empty), voice_file_id (may be None)
    Returns None if the update contains no usable message.
    """
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return None

    from_user  = msg.get("from", {})
    text       = msg.get("text", "").strip()
    voice      = msg.get("voice") or msg.get("audio")  # voice note or audio file
    voice_file = voice["file_id"] if voice else None

    if not text and not voice_file:
        return None  # sticker, photo, join event, etc.

    return {
        "update_id":     update.get("update_id", 0),
        "chat_id":       msg["chat"]["id"],
        "user":          from_user.get("first_name", "Unknown"),
        "text":          text,
        "voice_file_id": voice_file,
        "duration":      voice.get("duration", 0) if voice else 0,
    }


# ── Core message handler ───────────────────────────────────────────────────────

async def handle_update(token: str, update: dict[str, Any]) -> None:
    """Process a single Telegram update — text or voice — and reply appropriately.

    - Text message  → agent → reply as text
    - Voice message → Azure STT → agent → Azure TTS → reply as voice note
    """
    from src.channels.handler import channel_handler  # noqa: PLC0415

    parsed = parse_update(update)
    if not parsed:
        return

    chat_id = parsed["chat_id"]
    user    = parsed["user"]

    # ── Voice message path ─────────────────────────────────────────────────────
    if parsed["voice_file_id"]:
        logger.info("Telegram [%s] %s: <voice %ds>", chat_id, user, parsed["duration"])

        # Show 'recording audio…' indicator while processing
        await send_typing(token, chat_id)

        try:
            from config.settings import get_settings  # noqa: PLC0415
            s = get_settings()

            # 1. Download OGG from Telegram
            ogg_bytes = await download_voice(token, parsed["voice_file_id"])

            # 2. Transcribe with Azure STT
            # Detect language from pipeline config
            from config.settings import get_settings as _gs  # noqa: PLC0415
            import yaml  # noqa: PLC0415
            from pathlib import Path  # noqa: PLC0415
            _pipeline = yaml.safe_load(
                (Path(__file__).resolve().parents[2] / "config" / "pipeline.yaml").read_text()
            )
            language = _pipeline.get("stt", {}).get("language", "en-US")

            transcript = await transcribe_ogg(
                ogg_bytes,
                speech_key=s.azure_speech_key,
                speech_region=s.azure_speech_region,
                language=language,
            )

            if not transcript:
                await send_message(token, chat_id, "Sorry, I couldn't understand that. Please try again.")
                return

            logger.info("Telegram STT [%s]: %s", chat_id, transcript)

            # 3. Process through agent
            reply_text = await channel_handler.process(transcript, session_id=str(chat_id))
            logger.info("Telegram reply [%s]: %s", chat_id, reply_text)

            # 4. Synthesize reply with Azure TTS → OGG
            voice_name = _pipeline.get("tts", {}).get("voice", "en-US-AriaNeural")
            reply_ogg  = await synthesize_to_ogg(
                reply_text,
                speech_key=s.azure_speech_key,
                speech_region=s.azure_speech_region,
                voice=voice_name,
            )

            # 5. Send voice reply
            await send_voice(token, chat_id, reply_ogg)

        except Exception as exc:
            logger.error("Telegram voice handler error: %s", exc)
            await send_message(token, chat_id, "Sorry, something went wrong with the voice processing.")

    # ── Text message path ──────────────────────────────────────────────────────
    else:
        logger.info("Telegram [%s] %s: %s", chat_id, user, parsed["text"])
        try:
            reply = await channel_handler.process(parsed["text"], session_id=str(chat_id))
            await send_message(token, chat_id, reply)
        except Exception as exc:
            logger.error("Telegram text handler error: %s", exc)
            await send_message(token, chat_id, "Sorry, something went wrong. Please try again.")


# ── Backward-compat wrapper for webhook route ──────────────────────────────────

async def handle_webhook(token: str, body: dict[str, Any]) -> None:
    """Process one Telegram update delivered via webhook."""
    await handle_update(token, body)


# ── Polling mode ───────────────────────────────────────────────────────────────

class TelegramPoller:
    """Long-polls the Telegram getUpdates API.

    Handles both text and voice messages.
    No public URL or tunnel required — ideal for local development.
    """

    def __init__(self, token: str) -> None:
        self._token   = token
        self._offset  = 0
        self._running = False
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Spawn the polling loop as a background asyncio task."""
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop(), name="telegram-poller")
        logger.info("Telegram poller started (text + voice)")

    def stop(self) -> None:
        """Cancel the polling loop."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Telegram poller stopped")

    async def _poll_loop(self) -> None:
        logger.info("Telegram polling for updates…")
        while self._running:
            try:
                data = await _api(
                    self._token,
                    "getUpdates",
                    offset=self._offset,
                    timeout=20,
                    allowed_updates=["message"],
                )
                updates: list[dict[str, Any]] = data.get("result") or []
                for update in updates:
                    self._offset = update["update_id"] + 1
                    asyncio.create_task(
                        handle_update(self._token, update),
                        name=f"tg-update-{update['update_id']}",
                    )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Telegram: poll error: %s — retrying in 5s", exc)
                await asyncio.sleep(5)


# Module-level poller singleton — started by the UI server when token is set
_poller: TelegramPoller | None = None


def get_poller(token: str) -> TelegramPoller:
    """Return (creating if needed) the module-level TelegramPoller."""
    global _poller
    if _poller is None or _poller._token != token:
        if _poller:
            _poller.stop()
        _poller = TelegramPoller(token)
    return _poller
