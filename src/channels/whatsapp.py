"""Twilio WhatsApp channel adapter.

Protocol: Twilio sends HTTP POST (application/x-www-form-urlencoded) to
/webhook/whatsapp when a WhatsApp message arrives.  We verify the request
signature, route the body text through ChannelHandler, and return TwiML.

Setup checklist (see docs/channels.md):
  - Buy / connect a Twilio number with WhatsApp capability
  - Set the webhook URL to https://<tunnel>/webhook/whatsapp
  - Set TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + TWILIO_PHONE_NUMBER in .env
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import urllib.parse
from base64 import b64encode
from typing import Any

logger = logging.getLogger(__name__)


# ── Signature verification ─────────────────────────────────────────────────────

def _compute_signature(auth_token: str, url: str, params: dict[str, str]) -> str:
    """Reproduce Twilio's HMAC-SHA1 signature for the given request."""
    # Sort params alphabetically and append to URL
    sorted_params = "".join(f"{k}{v}" for k, v in sorted(params.items()))
    s = url + sorted_params
    mac = hmac.new(auth_token.encode(), s.encode(), hashlib.sha1)
    return b64encode(mac.digest()).decode()


def verify_request(
    auth_token: str,
    url: str,
    params: dict[str, str],
    signature: str | None,
) -> bool:
    """Return True when the X-Twilio-Signature header is valid."""
    if not auth_token or not signature:
        return False
    expected = _compute_signature(auth_token, url, params)
    return hmac.compare_digest(expected, signature)


# ── TwiML builder ──────────────────────────────────────────────────────────────

def twiml_message(body: str) -> str:
    """Wrap a reply in a minimal TwiML MessagingResponse."""
    # Escape XML special chars
    safe = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Message>{safe}</Message>"
        "</Response>"
    )


def twiml_empty() -> str:
    """Return an empty TwiML response (no reply)."""
    return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


# ── Incoming message parser ────────────────────────────────────────────────────

def parse_incoming(form: dict[str, Any]) -> dict[str, str]:
    """Extract the fields we care about from a Twilio WhatsApp POST body."""
    return {
        "message_sid": form.get("MessageSid", ""),
        "from_number": form.get("From", ""),
        "to_number":   form.get("To", ""),
        "body":        form.get("Body", "").strip(),
        "num_media":   form.get("NumMedia", "0"),
    }
