"""Agent router — manages multiple live agent instances and routes channel
messages to the correct one.

Each agent defined in config/agents.json can be started independently.
When started, the router:
  1. Creates a dedicated MCPRegistry (filtered to the agent's mcp_servers list).
  2. Connects all allowed MCP servers.
  3. Builds the agent's system prompt from the live server summaries.
  4. Instantiates an MCPAgent with per-session memory isolation.

Routing:
  route(channel, text, session_id) finds the first running agent whose
  ``channels`` list includes ``channel`` and processes the message through it.

Usage:
    from src.agent.router import agent_router
    reply = await agent_router.route("telegram", "List my open deals", session_id="42")
"""
from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger(__name__)


class AgentRouter:
    """Manages the lifecycle of all running agents and routes channel messages."""

    def __init__(self) -> None:
        # agent_id → (MCPAgent, MCPRegistry)
        self._live: dict[str, tuple[Any, Any]] = {}
        self._lock = asyncio.Lock()
        self._log_fn: Callable[[str, str], None] | None = None

    def set_log_fn(self, fn: Callable[[str, str], None]) -> None:
        """Set a callback for per-agent log lines: fn(agent_id, line)."""
        self._log_fn = fn

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def start_agent(self, agent_id: str) -> None:
        """Instantiate an agent, connect its MCP servers, and mark it running."""
        async with self._lock:
            if agent_id in self._live:
                logger.info("Agent %s already running — skipping", agent_id)
                return

            from src.agent.store import get_agent, set_status, build_system_prompt  # noqa: PLC0415
            from src.agent.memory import ConversationMemory                          # noqa: PLC0415
            from src.agent.agent import MCPAgent                                     # noqa: PLC0415
            from src.mcp.registry import MCPRegistry                                 # noqa: PLC0415
            from src.providers.llm.anthropic import AnthropicLLMProvider             # noqa: PLC0415

            agent_cfg = get_agent(agent_id)
            if not agent_cfg:
                raise ValueError(f"Agent '{agent_id}' not found")

            logger.info("Starting agent '%s' (%s)…", agent_cfg["name"], agent_id)

            if agent_cfg.get("pattern") == "openclaw_agent":
                from src.agent.openclaw import OpenClawGateway  # noqa: PLC0415
                import os  # noqa: PLC0415

                ws_url = agent_cfg.get("openclaw_url", "ws://openclaw-gateway:18789")
                token = agent_cfg.get("openclaw_token") or os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")
                gateway_agent_id = agent_cfg.get("openclaw_agent_id", "voice-agent")

                gw = OpenClawGateway(ws_url=ws_url, token=token, agent_id=gateway_agent_id)
                await gw.connect()

                self._live[agent_id] = (gw, None)
                set_status(agent_id, "running")
                logger.info("OpenClaw agent '%s' connected ✓", agent_cfg["name"])
                return

            # Per-agent MCP registry (filtered to agent's server list if set)
            allowed = agent_cfg.get("mcp_servers") or None  # [] → None (all)
            mcp = MCPRegistry(allowed_servers=allowed)
            await mcp.connect_all()

            # System prompt built from live server summaries
            system_prompt = build_system_prompt(agent_cfg, mcp.get_server_summaries())

            # LLM — respect per-agent model override
            model: str = agent_cfg.get("model", "claude-sonnet-4-6")
            llm = AnthropicLLMProvider(model=model)

            # Memory
            mem_cfg: dict[str, Any] = agent_cfg.get("memory", {"enabled": True, "max_turns": 10})
            memory = ConversationMemory(
                enabled=mem_cfg.get("enabled", True),
                max_turns=mem_cfg.get("max_turns", 10),
            )

            agent_obj = MCPAgent(
                llm=llm,
                mcp=mcp,
                max_iterations=10,
                memory=memory,
                system_prompt=system_prompt,
            )

            self._live[agent_id] = (agent_obj, mcp)
            set_status(agent_id, "running")
            logger.info("Agent '%s' started ✓", agent_cfg["name"])

    async def stop_agent(self, agent_id: str) -> None:
        """Disconnect an agent's MCP servers and mark it stopped."""
        async with self._lock:
            from src.agent.store import set_status  # noqa: PLC0415

            if agent_id not in self._live:
                set_status(agent_id, "stopped")
                return

            agent_obj, resource = self._live.pop(agent_id)
            if hasattr(resource, "disconnect_all"):
                await resource.disconnect_all()
            elif hasattr(agent_obj, "close"):
                await agent_obj.close()
            set_status(agent_id, "stopped")
            logger.info("Agent '%s' stopped", agent_id)

    async def close_all(self) -> None:
        """Stop all running agents (called on app shutdown)."""
        for agent_id in list(self._live.keys()):
            try:
                await self.stop_agent(agent_id)
            except Exception as exc:
                logger.error("Error stopping agent %s: %s", agent_id, exc)

    async def restore_running_agents(self) -> None:
        """Re-start any agents that were marked 'running' in agents.json.

        Called on app startup so a server restart brings agents back up.
        """
        from src.agent.store import list_agents  # noqa: PLC0415
        for agent_cfg in list_agents():
            if agent_cfg.get("status") == "running":
                try:
                    await self.start_agent(agent_cfg["id"])
                except Exception as exc:
                    logger.error(
                        "Failed to restore agent '%s': %s", agent_cfg["id"], exc
                    )

    # ── Routing ────────────────────────────────────────────────────────────────

    async def route(
        self,
        channel: str,
        text: str,
        session_id: str = "default",
    ) -> str:
        """Route a message to the running agent that handles *channel*.

        Falls back to the first running agent if no channel-specific match is
        found (e.g. during early development before channels are configured).
        Returns the agent's text reply.
        """
        agent_id, pair = self._find_agent_for_channel(channel)
        if pair is None:
            # Fallback: any running agent
            entry = next(iter(self._live.items()), None)
            if entry:
                agent_id, pair = entry
        if pair is None:
            logger.warning("No running agent for channel '%s' — message dropped", channel)
            return "No agent is currently running. Start one from the Agents page."

        agent_obj, _ = pair
        if self._log_fn and agent_id:
            self._log_fn(agent_id, f"📨 [{channel}] {text[:200]}")
        try:
            response = await agent_obj.process(text, session_id=session_id)
            if isinstance(response, str):
                reply = response or "Done."
            else:
                reply = response.result_summary or "Done."
            if self._log_fn and agent_id:
                self._log_fn(agent_id, f"🤖 {reply[:200]}")
            return reply
        except Exception as exc:
            logger.error("Agent error on channel '%s': %s", channel, exc)
            if self._log_fn and agent_id:
                self._log_fn(agent_id, f"❌ Error: {exc}")
            return f"Sorry, something went wrong: {exc}"

    def is_running(self, agent_id: str) -> bool:
        """Return True if the agent is currently live in this router."""
        return agent_id in self._live

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _find_agent_for_channel(
        self, channel: str
    ) -> tuple[str | None, tuple[Any, Any] | None]:
        """Return (agent_id, (MCPAgent, MCPRegistry)) for the first running agent
        that lists *channel* in its channels config."""
        from src.agent.store import get_agent  # noqa: PLC0415
        for agent_id, pair in self._live.items():
            cfg = get_agent(agent_id)
            if cfg and channel in cfg.get("channels", []):
                return agent_id, pair
        return None, None


# Module-level singleton — shared by all channel webhooks and the API layer.
agent_router = AgentRouter()
