"""Shared channel handler — singleton that keeps the agent + MCP connections alive
so every incoming message doesn't pay a cold-start penalty.

Usage:
    from src.channels.handler import channel_handler
    reply = await channel_handler.process("List my open opportunities")

Concurrency
───────────
The singleton is safe for concurrent use from multiple channel webhooks.
Concurrent requests share the same MCPRegistry, which serialises per-server
stdio I/O via an asyncio.Lock inside each MCPClient.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Ensure project root is on path when imported from the UI server
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger(__name__)


class ChannelHandler:
    """Maintains a long-lived agent + MCP connection for channel messages."""

    def __init__(self) -> None:
        self._agent  = None
        self._mcp    = None
        self._lock   = asyncio.Lock()
        self._ready  = False

    async def _connect(self) -> None:
        from src.mcp.registry import MCPRegistry          # noqa: PLC0415
        from src.agent.agent import MCPAgent              # noqa: PLC0415
        from src.providers.factory import ProviderFactory # noqa: PLC0415

        factory     = ProviderFactory()
        llm         = factory.get_llm()
        self._mcp   = MCPRegistry()
        await self._mcp.connect_all()
        max_iter    = factory.agent_config.get("max_tool_iterations", 10)
        self._agent = MCPAgent(llm=llm, mcp=self._mcp, max_iterations=max_iter)
        self._ready = True
        logger.info("ChannelHandler: agent ready")

    async def _ensure_ready(self) -> None:
        if self._ready:
            return
        async with self._lock:
            if not self._ready:          # double-checked locking
                await self._connect()

    async def process(self, text: str, session_id: str = "default") -> str:
        """Process a text utterance and return a short spoken response."""
        await self._ensure_ready()
        try:
            response = await self._agent.process(text, session_id=session_id)   # type: ignore[union-attr]
            return response.result_summary or "Done."
        except Exception as exc:
            logger.error("ChannelHandler error: %s", exc)
            return f"Sorry, something went wrong: {exc}"

    async def close(self) -> None:
        if self._mcp:
            await self._mcp.disconnect_all()
        self._agent = None
        self._mcp   = None
        self._ready = False
        logger.info("ChannelHandler: closed")

    def invalidate(self) -> None:
        """Force reconnect on next message (call after config changes)."""
        self._ready = False


# Module-level singleton — shared by all channel webhooks
channel_handler = ChannelHandler()
