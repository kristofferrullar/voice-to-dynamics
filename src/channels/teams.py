"""Microsoft Teams bot channel adapter.

Protocol: Bot Framework HTTP (no heavy SDK — raw JWT + REST).

Flow:
  1. Teams → POST /webhook/teams  (Bot Framework Activity JSON)
  2. Verify Bearer JWT from Microsoft
  3. Extract message text
  4. Process through ChannelHandler
  5. Reply via Bot Connector REST API

Setup checklist (see docs/channels.md):
  - Create Azure Bot registration: az bot create ...
  - Set messaging endpoint to https://<tunnel>/webhook/teams
  - Add Teams channel in Azure Portal
  - Set TEAMS_APP_ID + TEAMS_APP_PASSWORD in .env
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
import jwt as pyjwt

logger = logging.getLogger(__name__)

# Microsoft Bot Framework token endpoints
_OIDC_URL  = "https://login.botframework.com/v1/.well-known/openid-configuration"
_TOKEN_URL = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
_SCOPE     = "https://api.botframework.com/.default"

# Simple in-memory JWKS cache (refresh if key not found)
_jwks_cache: dict[str, Any] | None = None


async def _get_jwks() -> dict[str, Any]:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    async with httpx.AsyncClient(timeout=10) as client:
        oidc = (await client.get(_OIDC_URL)).json()
        _jwks_cache = (await client.get(oidc["jwks_uri"])).json()
    return _jwks_cache


async def verify_request(authorization: str | None, app_id: str) -> bool:
    """Return True if the Bearer token is a valid Bot Framework JWT for our app."""
    if not app_id or not authorization or not authorization.startswith("Bearer "):
        return False
    token = authorization[7:]
    try:
        header = pyjwt.get_unverified_header(token)
        jwks = await _get_jwks()
        key_data = next(
            (k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")),
            None,
        )
        if not key_data:
            # Refresh JWKS once in case of key rotation
            global _jwks_cache
            _jwks_cache = None
            jwks = await _get_jwks()
            key_data = next(
                (k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")),
                None,
            )
        if not key_data:
            logger.warning("Teams: no matching JWKS key for kid=%s", header.get("kid"))
            return False
        public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(key_data)  # type: ignore[attr-defined]
        pyjwt.decode(token, public_key, algorithms=["RS256"], audience=app_id)
        return True
    except Exception as exc:
        logger.warning("Teams JWT verification failed: %s", exc)
        return False


async def _get_connector_token(app_id: str, app_password: str) -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "grant_type":    "client_credentials",
                "client_id":     app_id,
                "client_secret": app_password,
                "scope":         _SCOPE,
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def send_reply(
    service_url: str,
    conversation_id: str,
    reply_to_id: str,
    text: str,
    app_id: str,
    app_password: str,
) -> None:
    """Send a text reply via the Bot Connector REST API."""
    token = await _get_connector_token(app_id, app_password)
    url = (
        f"{service_url.rstrip('/')}/v3/conversations"
        f"/{conversation_id}/activities/{reply_to_id}"
    )
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"type": "message", "text": text},
        )
        if resp.status_code not in (200, 201):
            logger.error("Teams reply failed %s: %s", resp.status_code, resp.text)
