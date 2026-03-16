"""Azure Communication Services (ACS) voice call adapter.

Flow (inbound PSTN/VoIP call):
  1. ACS sends an IncomingCall event to POST /webhook/acs/call
  2. We answer via the Call Automation REST API
  3. ACS delivers mid-call events to POST /webhook/acs/events
     – CallConnected  → play greeting TTS
     – RecognizeCompleted → route recognised text through ChannelHandler
     – PlayCompleted  → trigger next Recognize or hang up

Setup checklist (see docs/channels.md):
  - Create an ACS resource and acquire a phone number
  - Register event subscription for IncomingCall to https://<tunnel>/webhook/acs/call
  - Set ACS_CONNECTION_STRING and ACS_CALLBACK_URL in .env
  - The callback URL must be HTTPS (use ngrok / Azure Dev Tunnel locally)

Note: This module is intentionally thin — it only shapes data for the FastAPI
routes in ui/app.py, which hold the actual HTTP handler logic.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Event type constants (ACS Cloud Event types) ───────────────────────────────
EVENT_INCOMING_CALL      = "Microsoft.Communication.IncomingCall"
EVENT_CALL_CONNECTED     = "Microsoft.Communication.CallConnected"
EVENT_CALL_DISCONNECTED  = "Microsoft.Communication.CallDisconnected"
EVENT_RECOGNIZE_COMPLETED = "Microsoft.Communication.RecognizeCompleted"
EVENT_RECOGNIZE_FAILED   = "Microsoft.Communication.RecognizeFailed"
EVENT_PLAY_COMPLETED     = "Microsoft.Communication.PlayCompleted"
EVENT_PLAY_FAILED        = "Microsoft.Communication.PlayFailed"

# ── Greeting spoken when a call is first connected ────────────────────────────
GREETING_TEXT = (
    "Hello! I'm your AI assistant. How can I help you today? "
    "Please speak after the tone."
)
GREETING_TEXT_SV = (
    "Hej! Jag är din AI-assistent. Hur kan jag hjälpa dig? "
    "Vänligen tala efter tonen."
)


def parse_cloud_event(body: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return (event_type, event_data) from a CloudEvent envelope."""
    event_type = body.get("type", "")
    data = body.get("data", {})
    return event_type, data


def build_answer_request(
    incoming_call_context: str,
    callback_url: str,
    cognitive_services_endpoint: str = "",
) -> dict[str, Any]:
    """Build the JSON body for the ACS AnswerCall REST call."""
    req: dict[str, Any] = {
        "incomingCallContext": incoming_call_context,
        "callbackUri": callback_url,
    }
    if cognitive_services_endpoint:
        req["azureCognitiveServicesEndpointUrl"] = cognitive_services_endpoint
    return req


def build_play_tts_request(
    text: str,
    voice_name: str = "en-US-AriaNeural",
    operation_context: str = "greeting",
) -> dict[str, Any]:
    """Build the JSON body for the ACS PlayMedia (TTS) REST call."""
    return {
        "playTo": [],          # empty = play to all participants
        "playSources": [
            {
                "kind": "textToSpeech",
                "textToSpeech": {
                    "text": text,
                    "voiceName": voice_name,
                    "customVoiceEndpointId": "",
                },
            }
        ],
        "operationContext": operation_context,
    }


def build_recognize_request(
    prompt_text: str,
    voice_name: str = "en-US-AriaNeural",
    operation_context: str = "main",
    speech_language: str = "en-US",
    silence_timeout_sec: int = 5,
) -> dict[str, Any]:
    """Build the JSON body for the ACS StartRecognizing REST call."""
    return {
        "recognizeInputType": "speech",
        "playPrompt": {
            "kind": "textToSpeech",
            "textToSpeech": {
                "text": prompt_text,
                "voiceName": voice_name,
            },
        },
        "recognizeOptions": {
            "speech": {
                "speechLanguage": speech_language,
                "endSilenceTimeoutInMs": silence_timeout_sec * 1000,
            }
        },
        "operationContext": operation_context,
    }


def build_hangup_request() -> dict[str, Any]:
    """Build the JSON body for an ACS HangUp call."""
    return {"forEveryone": True}


def extract_speech_result(recognize_data: dict[str, Any]) -> str:
    """Pull the recognised speech text out of a RecognizeCompleted event payload."""
    result = recognize_data.get("recognitionResult", {})
    alternatives = result.get("alternatives", [])
    if alternatives:
        return alternatives[0].get("text", "").strip()
    return result.get("speech", {}).get("text", "").strip()
