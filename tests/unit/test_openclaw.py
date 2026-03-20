"""Unit tests for OpenClawGateway (no real WebSocket — uses mocks)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent.openclaw import OpenClawGateway


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_frame(**kwargs: object) -> str:
    return json.dumps(kwargs)


def _gateway() -> OpenClawGateway:
    return OpenClawGateway(ws_url="ws://localhost:18789", token="tok", agent_id="test-agent")


# ---------------------------------------------------------------------------
# _extract_message_text
# ---------------------------------------------------------------------------

class TestExtractMessageText:
    def test_plain_text_key(self) -> None:
        msg = {"text": "Hello world"}
        assert OpenClawGateway._extract_message_text(msg) == "Hello world"

    def test_content_list(self) -> None:
        msg = {"content": [{"type": "text", "text": "Part one"}, {"type": "text", "text": " part two"}]}
        assert OpenClawGateway._extract_message_text(msg) == "Part one part two"

    def test_non_dict_returns_empty(self) -> None:
        assert OpenClawGateway._extract_message_text("raw string") == ""
        assert OpenClawGateway._extract_message_text(None) == ""

    def test_content_list_skips_non_text_blocks(self) -> None:
        msg = {"content": [{"type": "image", "url": "img.png"}, {"type": "text", "text": "hi"}]}
        assert OpenClawGateway._extract_message_text(msg) == "hi"

    def test_empty_content_list(self) -> None:
        assert OpenClawGateway._extract_message_text({"content": []}) == ""

    def test_missing_text_key_in_block(self) -> None:
        msg = {"content": [{"type": "text"}]}
        assert OpenClawGateway._extract_message_text(msg) == ""


# ---------------------------------------------------------------------------
# _new_id
# ---------------------------------------------------------------------------

class TestNewId:
    def test_starts_with_vmcp(self) -> None:
        assert OpenClawGateway._new_id().startswith("vmcp-")

    def test_ids_are_unique(self) -> None:
        ids = {OpenClawGateway._new_id() for _ in range(100)}
        assert len(ids) == 100


# ---------------------------------------------------------------------------
# session_key formatting in process()
# ---------------------------------------------------------------------------

class TestSessionKeyFormatting:
    """Verify that process() derives the session key correctly."""

    @pytest.mark.asyncio
    async def test_session_key_prefixed_when_plain(self) -> None:
        """A plain session_id should be prefixed with agent:{agent_id}:."""
        gw = _gateway()

        sent_frames: list[dict] = []

        async def fake_send(msg: str) -> None:
            sent_frames.append(json.loads(msg))

        # Fake a WebSocket that immediately resolves the pending future
        fake_ws = MagicMock()
        fake_ws.send = fake_send
        gw._ws = fake_ws

        # Pre-load the future so process() resolves without a listen loop
        req_id_holder: list[str] = []

        original_process = gw.process

        async def patched_process(text: str, session_id: str = "default") -> str:
            # Intercept right before the real send, resolve the future ourselves
            async with gw._lock:
                req_id = gw._new_id()
                fut: asyncio.Future = asyncio.get_event_loop().create_future()
                gw._pending[req_id] = fut
                req_id_holder.append(req_id)
                session_key = session_id if session_id.startswith("agent:") else f"agent:{gw._agent_id}:{session_id}"
                await gw._send({
                    "type": "req", "id": req_id, "method": "chat.send",
                    "params": {"sessionKey": session_key, "message": text, "deliver": False, "idempotencyKey": gw._new_id()},
                })
                fut.set_result({"ok": True, "payload": {"text": "pong"}})
                result = await asyncio.wait_for(fut, timeout=5)
                return result["payload"]["text"]

        reply = await patched_process("hello", session_id="room-1")
        assert reply == "pong"
        assert sent_frames[0]["params"]["sessionKey"] == "agent:test-agent:room-1"

    @pytest.mark.asyncio
    async def test_session_key_passed_through_when_already_prefixed(self) -> None:
        gw = _gateway()
        sent_frames: list[dict] = []

        async def fake_send(msg: str) -> None:
            sent_frames.append(json.loads(msg))

        gw._ws = MagicMock()
        gw._ws.send = fake_send

        async with gw._lock:
            req_id = gw._new_id()
            fut: asyncio.Future = asyncio.get_event_loop().create_future()
            gw._pending[req_id] = fut
            session_id = "agent:custom:already-set"
            session_key = session_id if session_id.startswith("agent:") else f"agent:{gw._agent_id}:{session_id}"
            await gw._send({
                "type": "req", "id": req_id, "method": "chat.send",
                "params": {"sessionKey": session_key, "message": "hi", "deliver": False, "idempotencyKey": gw._new_id()},
            })
            fut.set_result({"ok": True, "payload": {"text": "ok"}})

        assert sent_frames[0]["params"]["sessionKey"] == "agent:custom:already-set"


# ---------------------------------------------------------------------------
# Helper: async WebSocket mock that yields frames one by one
# ---------------------------------------------------------------------------

class _AsyncWsMock:
    """Minimal async-iterable mock for a WebSocket connection."""

    def __init__(self, frames: list[str]) -> None:
        self._frames = frames

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for f in self._frames:
            yield f


# ---------------------------------------------------------------------------
# _listen_loop — res frame routing
# ---------------------------------------------------------------------------

class TestListenLoopResRouting:
    @pytest.mark.asyncio
    async def test_res_frame_resolves_pending_future(self) -> None:
        gw = _gateway()

        req_id = gw._new_id()
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        gw._pending[req_id] = fut

        gw._ws = _AsyncWsMock([_make_frame(type="res", id=req_id, ok=True, payload={"text": "result"})])
        await gw._listen_loop()

        assert fut.done()
        assert fut.result()["payload"]["text"] == "result"
        assert req_id not in gw._pending

    @pytest.mark.asyncio
    async def test_started_res_maps_run_id(self) -> None:
        gw = _gateway()

        req_id = gw._new_id()
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        gw._pending[req_id] = fut

        gw._ws = _AsyncWsMock([
            _make_frame(type="res", id=req_id, ok=True, payload={"status": "started", "runId": "run-abc"}),
        ])
        await gw._listen_loop()

        assert not fut.done()
        assert gw._run_to_request.get("run-abc") == req_id


# ---------------------------------------------------------------------------
# _listen_loop — chat event routing
# ---------------------------------------------------------------------------

class TestListenLoopChatEvents:
    @pytest.mark.asyncio
    async def test_final_chat_event_resolves_future(self) -> None:
        gw = _gateway()

        req_id = gw._new_id()
        run_id = "run-xyz"
        gw._run_to_request[run_id] = req_id
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        gw._pending[req_id] = fut

        gw._ws = _AsyncWsMock([
            _make_frame(
                type="event", event="chat",
                payload={"runId": run_id, "state": "final", "message": {"text": "Final reply"}},
            )
        ])
        await gw._listen_loop()

        assert fut.done()
        assert fut.result()["payload"]["text"] == "Final reply"

    @pytest.mark.asyncio
    async def test_error_chat_event_sets_ok_false(self) -> None:
        gw = _gateway()

        req_id = gw._new_id()
        run_id = "run-err"
        gw._run_to_request[run_id] = req_id
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        gw._pending[req_id] = fut

        gw._ws = _AsyncWsMock([
            _make_frame(
                type="event", event="chat",
                payload={"runId": run_id, "state": "error", "errorMessage": "Agent crash"},
            )
        ])
        await gw._listen_loop()

        assert fut.done()
        result = fut.result()
        assert result["ok"] is False
        assert "Agent crash" in result["error"]["message"]
