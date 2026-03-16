"""MCP server registry.

Reads config/mcp_servers.yaml, connects to all enabled MCP servers at startup,
and exposes a merged tool list + unified call_tool interface to the agent.

Adding a new MCP server:
1. Add an entry to config/mcp_servers.yaml.
2. Restart the voice session — the registry auto-discovers it.
See docs/adding_mcp_server.md for details.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from src.mcp.client import MCPClient

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "mcp_servers.yaml"


class MCPRegistry:
    """Manages connections to all enabled MCP servers."""

    def __init__(self) -> None:
        self._servers: dict[str, MCPClient] = {}
        self._tool_to_server: dict[str, str] = {}  # tool_name → server_name

    async def connect_all(self) -> None:
        """Connect to every enabled server listed in mcp_servers.yaml."""
        config = self._load_config()
        for srv in config.get("servers", []):
            if not srv.get("enabled", False):
                continue
            name: str = srv["name"]
            client = MCPClient(
                name=name,
                transport=srv["transport"],
                command=srv.get("command"),
                url=srv.get("url"),
            )
            try:
                await client.connect()
                tools = await client.list_tools()
            except Exception as exc:
                logger.warning("⚠️  MCP server '%s' failed to connect — skipping. (%s)", name, exc)
                continue
            self._servers[name] = client
            for tool in tools:
                tool_name = tool["name"]
                if tool_name in self._tool_to_server:
                    logger.warning(
                        "Tool '%s' is provided by both '%s' and '%s' — '%s' wins",
                        tool_name,
                        self._tool_to_server[tool_name],
                        name,
                        name,
                    )
                self._tool_to_server[tool_name] = name
            logger.info("Connected MCP server '%s' (%d tools)", name, len(tools))

    async def disconnect_all(self) -> None:
        for client in self._servers.values():
            await client.disconnect()
        self._servers.clear()
        self._tool_to_server.clear()

    async def get_tools(self) -> list[dict[str, Any]]:
        """Return a merged list of all tools from all connected servers."""
        tools: list[dict[str, Any]] = []
        for client in self._servers.values():
            tools.extend(await client.list_tools())
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool by name, routing to the correct server."""
        server_name = self._tool_to_server.get(name)
        if not server_name:
            raise ValueError(f"Unknown tool: '{name}'. Available: {list(self._tool_to_server)}")
        return await self._servers[server_name].call_tool(name, arguments)

    @staticmethod
    def _load_config() -> dict[str, Any]:
        with open(_CONFIG_PATH) as f:
            return yaml.safe_load(f)
