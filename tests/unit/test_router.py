"""Unit tests for AgentRouter — log fn and channel routing."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent.router import AgentRouter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent_cfg(agent_id: str, channels: list[str], pattern: str = "voice_assistant") -> dict:
    return {
        "id": agent_id,
        "name": f"Agent {agent_id}",
        "pattern": pattern,
        "model": "claude-sonnet-4-6",
        "channels": channels,
        "mcp_servers": [],
        "memory": {"enabled": True, "max_turns": 10},
        "status": "running",
    }


# ---------------------------------------------------------------------------
# set_log_fn / _log_fn
# ---------------------------------------------------------------------------

class TestLogFn:
    def test_set_log_fn_stores_callback(self) -> None:
        router = AgentRouter()
        fn = MagicMock()
        router.set_log_fn(fn)
        assert router._log_fn is fn

    def test_default_log_fn_is_none(self) -> None:
        router = AgentRouter()
        assert router._log_fn is None


# ---------------------------------------------------------------------------
# _find_agent_for_channel
# ---------------------------------------------------------------------------

class TestFindAgentForChannel:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_live_agents(self) -> None:
        router = AgentRouter()
        agent_id, pair = router._find_agent_for_channel("telegram")
        assert agent_id is None
        assert pair is None

    @pytest.mark.asyncio
    async def test_finds_agent_matching_channel(self) -> None:
        router = AgentRouter()
        mock_agent = MagicMock()
        mock_mcp = MagicMock()
        router._live["agent-1"] = (mock_agent, mock_mcp)

        with patch("src.agent.router.AgentRouter._find_agent_for_channel",
                   wraps=router._find_agent_for_channel):
            with patch("src.agent.store.get_agent") as mock_get:
                mock_get.return_value = _agent_cfg("agent-1", ["telegram", "local"])
                agent_id, pair = router._find_agent_for_channel("telegram")

        assert agent_id == "agent-1"
        assert pair == (mock_agent, mock_mcp)

    @pytest.mark.asyncio
    async def test_returns_none_for_unmatched_channel(self) -> None:
        router = AgentRouter()
        mock_agent = MagicMock()
        router._live["agent-1"] = (mock_agent, None)

        with patch("src.agent.store.get_agent") as mock_get:
            mock_get.return_value = _agent_cfg("agent-1", ["telegram"])
            agent_id, pair = router._find_agent_for_channel("whatsapp")

        assert agent_id is None
        assert pair is None


# ---------------------------------------------------------------------------
# route() — log emission
# ---------------------------------------------------------------------------

class TestRouteLogging:
    @pytest.mark.asyncio
    async def test_log_fn_called_with_incoming_and_reply(self) -> None:
        router = AgentRouter()

        log_calls: list[tuple[str, str]] = []
        router.set_log_fn(lambda agent_id, line: log_calls.append((agent_id, line)))

        mock_agent = AsyncMock()
        mock_agent.process = AsyncMock(return_value="Done!")
        router._live["agent-1"] = (mock_agent, MagicMock())

        with patch("src.agent.store.get_agent") as mock_get:
            mock_get.return_value = _agent_cfg("agent-1", ["local"])
            reply = await router.route("local", "Do something", session_id="s1")

        assert reply == "Done!"
        assert len(log_calls) == 2
        assert log_calls[0][0] == "agent-1"
        assert "📨" in log_calls[0][1]
        assert "Do something" in log_calls[0][1]
        assert log_calls[1][0] == "agent-1"
        assert "🤖" in log_calls[1][1]

    @pytest.mark.asyncio
    async def test_no_log_fn_does_not_crash(self) -> None:
        router = AgentRouter()
        mock_agent = AsyncMock()
        mock_agent.process = AsyncMock(return_value="ok")
        router._live["agent-1"] = (mock_agent, MagicMock())

        with patch("src.agent.store.get_agent") as mock_get:
            mock_get.return_value = _agent_cfg("agent-1", ["local"])
            reply = await router.route("local", "test", session_id="s1")

        assert reply == "ok"

    @pytest.mark.asyncio
    async def test_error_logged_and_safe_reply_returned(self) -> None:
        router = AgentRouter()
        log_calls: list[tuple[str, str]] = []
        router.set_log_fn(lambda agent_id, line: log_calls.append((agent_id, line)))

        mock_agent = AsyncMock()
        mock_agent.process = AsyncMock(side_effect=RuntimeError("boom"))
        router._live["agent-1"] = (mock_agent, MagicMock())

        with patch("src.agent.store.get_agent") as mock_get:
            mock_get.return_value = _agent_cfg("agent-1", ["local"])
            reply = await router.route("local", "crash me", session_id="s1")

        assert "boom" in reply
        assert any("❌" in line for _, line in log_calls)


# ---------------------------------------------------------------------------
# route() — fallback to first running agent
# ---------------------------------------------------------------------------

class TestRouteFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_first_agent_when_no_channel_match(self) -> None:
        router = AgentRouter()
        mock_agent = AsyncMock()
        mock_agent.process = AsyncMock(return_value="fallback reply")
        router._live["agent-1"] = (mock_agent, MagicMock())

        with patch("src.agent.store.get_agent") as mock_get:
            # agent only handles "telegram", not "whatsapp"
            mock_get.return_value = _agent_cfg("agent-1", ["telegram"])
            reply = await router.route("whatsapp", "hello", session_id="s1")

        assert reply == "fallback reply"

    @pytest.mark.asyncio
    async def test_returns_no_agent_message_when_no_live_agents(self) -> None:
        router = AgentRouter()
        reply = await router.route("telegram", "hello", session_id="s1")
        assert "No agent" in reply


# ---------------------------------------------------------------------------
# is_running
# ---------------------------------------------------------------------------

class TestIsRunning:
    def test_false_when_not_live(self) -> None:
        router = AgentRouter()
        assert router.is_running("agent-x") is False

    def test_true_when_live(self) -> None:
        router = AgentRouter()
        router._live["agent-x"] = (MagicMock(), MagicMock())
        assert router.is_running("agent-x") is True
