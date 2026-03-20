"""OpenClaw gateway client - wraps the WebSocket JSON-RPC v3 protocol.

Maintains a persistent authenticated connection to an OpenClaw gateway and
routes chat.send / chat.done exchanges as blocking async calls.

Usage:
    gw = OpenClawGateway(
        ws_url="ws://openclaw-gateway:18789",
        token="secret",
        agent_id="voice-agent",
    )
    await gw.connect()
    reply = await gw.process("Hello", session_id="telegram-42")
    await gw.close()
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = 3
OPERATOR_SCOPES = [
    "operator.read",
    "operator.write",
    "operator.admin",
    "operator.approvals",
    "operator.pairing",
]


class OpenClawGateway:
    """Persistent authenticated connection to one OpenClaw gateway."""

    def __init__(self, ws_url: str, token: str, agent_id: str = "voice-agent") -> None:
        self._ws_url = ws_url
        self._token = token
        self._agent_id = agent_id
        self._ws: Any = None
        self._lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future] = {}
        self._run_to_request: dict[str, str] = {}
        self._run_text: dict[str, str] = {}
        self._listen_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """Open the WebSocket and complete the connect.challenge handshake."""
        import websockets

        self._ws = await websockets.connect(
            self._ws_url,
            additional_headers={"Origin": self._ws_url.replace("ws://", "http://")},
        )

        challenge = await self._recv_frame()
        if not (challenge.get("type") == "event" and challenge.get("event") == "connect.challenge"):
            raise RuntimeError(f"Expected connect.challenge, got: {challenge}")

        connect_id = self._new_id()
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[connect_id] = fut
        self._listen_task = asyncio.create_task(self._listen_loop())
        await self._send({
            "type": "req",
            "id": connect_id,
            "method": "connect",
            "params": {
                "minProtocol": PROTOCOL_VERSION,
                "maxProtocol": PROTOCOL_VERSION,
                "client": {
                    "id": "openclaw-control-ui",
                    "version": "1.0.0",
                    "platform": "python",
                    "mode": "webchat",
                    "instanceId": str(uuid.uuid4()),
                },
                "role": "operator",
                "scopes": OPERATOR_SCOPES,
                "caps": ["tool-events"],
                "auth": {"token": self._token},
                "locale": "en-US",
                "userAgent": "python",
            },
        })

        result = await asyncio.wait_for(fut, timeout=15)
        if not result.get("ok"):
            raise RuntimeError(f"OpenClaw connect failed: {result.get('error')}")

        logger.info("OpenClaw gateway connected (%s)", self._ws_url)

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._listen_task:
            self._listen_task.cancel()
            self._listen_task = None
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def process(self, text: str, session_id: str = "default") -> str:
        """Send a message and wait for the complete reply."""
        async with self._lock:
            req_id = self._new_id()
            fut: asyncio.Future = asyncio.get_event_loop().create_future()
            self._pending[req_id] = fut
            session_key = session_id if session_id.startswith("agent:") else f"agent:{self._agent_id}:{session_id}"

            await self._send({
                "type": "req",
                "id": req_id,
                "method": "chat.send",
                "params": {
                    "sessionKey": session_key,
                    "message": text,
                    "deliver": False,
                    "idempotencyKey": self._new_id(),
                },
            })

            try:
                result = await asyncio.wait_for(fut, timeout=120)
            except asyncio.TimeoutError as exc:
                self._pending.pop(req_id, None)
                raise RuntimeError("OpenClaw: chat.send timed out after 120 s") from exc

            payload = result.get("payload") or result
            if result.get("ok") is False:
                error = result.get("error", {})
                raise RuntimeError(error.get("message") or str(error))
            if isinstance(payload, dict):
                return payload.get("text") or payload.get("reply") or str(payload)
            return str(payload)

    async def _listen_loop(self) -> None:
        """Background task - routes incoming frames to pending futures."""
        try:
            async for raw in self._ws:
                frame = json.loads(raw)
                ftype = frame.get("type")
                fid = frame.get("id")

                if ftype == "res" and fid and fid in self._pending:
                    payload = frame.get("payload", {})
                    if frame.get("ok") and isinstance(payload, dict) and payload.get("status") == "started":
                        run_id = payload.get("runId")
                        if run_id:
                            self._run_to_request[run_id] = fid
                            continue

                    fut = self._pending.pop(fid)
                    if not fut.done():
                        fut.set_result(frame)
                elif ftype == "event" and frame.get("event") == "chat":
                    payload = frame.get("payload", {})
                    run_id = payload.get("runId")
                    state = payload.get("state")
                    text = self._extract_message_text(payload.get("message"))
                    if run_id and text:
                        self._run_text[run_id] = text
                    if not run_id or state not in {"final", "aborted", "error"}:
                        continue

                    req_id = self._run_to_request.pop(run_id, None)
                    if not req_id:
                        continue

                    fut = self._pending.pop(req_id, None)
                    final_text = text or self._run_text.pop(run_id, "")
                    if fut and not fut.done():
                        if state == "error":
                            fut.set_result({
                                "ok": False,
                                "error": {"message": payload.get("errorMessage") or "OpenClaw chat error"},
                            })
                        else:
                            fut.set_result({"ok": True, "payload": {"text": final_text}})
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("OpenClaw listener crashed: %s", exc)
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(exc)
            self._pending.clear()

    async def _recv_frame(self) -> dict[str, Any]:
        raw = await self._ws.recv()
        return json.loads(raw)

    async def _send(self, frame: dict[str, Any]) -> None:
        await self._ws.send(json.dumps(frame))

    @staticmethod
    def _new_id() -> str:
        return f"vmcp-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _extract_message_text(message: Any) -> str:
        if not isinstance(message, dict):
            return ""
        if isinstance(message.get("text"), str):
            return message["text"]
        content = message.get("content")
        if not isinstance(content, list):
            return ""
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts).strip()
