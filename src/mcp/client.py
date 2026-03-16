"""Low-level MCP client wrapper.

Supports stdio (subprocess) and SSE (HTTP) transports.
The registry uses this to connect to individual MCP servers.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class MCPClient:
    """Connects to a single MCP server and exposes list_tools / call_tool."""

    def __init__(
        self,
        name: str,
        transport: str,
        command: list[str] | None = None,
        url: str | None = None,
    ) -> None:
        self.name = name
        self._transport = transport
        self._command = command
        self._url = url
        self._process: asyncio.subprocess.Process | None = None
        self._http: httpx.AsyncClient | None = None
        self._tools_cache: list[dict[str, Any]] | None = None
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def connect(self) -> None:
        if self._transport == "stdio":
            if not self._command:
                raise ValueError(f"MCP server '{self.name}' requires 'command' for stdio transport")
            self._process = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # MCP requires an initialize handshake before any other calls.
            await self._stdio_rpc({
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "voice-to-dynamics", "version": "0.1.0"},
                },
            })
            # Acknowledge with initialized notification (no response expected).
            notify = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}) + "\n"
            self._process.stdin.write(notify.encode())  # type: ignore[union-attr]
            await self._process.stdin.drain()  # type: ignore[union-attr]
        elif self._transport == "sse":
            if not self._url:
                raise ValueError(f"MCP server '{self.name}' requires 'url' for SSE transport")
            self._http = httpx.AsyncClient(base_url=self._url, timeout=30.0)
        else:
            raise ValueError(f"Unknown MCP transport: '{self._transport}'")

    async def disconnect(self) -> None:
        if self._process:
            self._process.terminate()
            await self._process.wait()
        if self._http:
            await self._http.aclose()

    async def list_tools(self) -> list[dict[str, Any]]:
        if self._tools_cache is not None:
            return self._tools_cache
        response = await self._rpc("tools/list", {})
        self._tools_cache = response.get("tools", [])
        return self._tools_cache

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        response = await self._rpc("tools/call", {"name": name, "arguments": arguments})
        content = response.get("content", [])
        # Extract text from content blocks
        if content and isinstance(content[0], dict):
            return content[0].get("text", response)
        return response

    async def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params,
        }
        if self._transport == "stdio":
            return await self._stdio_rpc(payload)
        return await self._sse_rpc(payload)

    async def _stdio_rpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise RuntimeError(f"MCP stdio process '{self.name}' is not running")
        line = json.dumps(payload) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()
        # Read lines until a valid JSON-RPC response is found.
        # Non-JSON lines (npm install output, warnings, etc.) are logged and skipped.
        while True:
            try:
                raw = await asyncio.wait_for(self._process.stdout.readline(), timeout=30.0)
            except asyncio.TimeoutError:
                raise RuntimeError(f"MCP server '{self.name}' timed out waiting for response")
            if not raw:
                raise RuntimeError(f"MCP server '{self.name}' closed stdout unexpectedly")
            text = raw.decode(errors="replace").strip()
            if not text:
                continue
            try:
                response = json.loads(text)
                break
            except json.JSONDecodeError:
                logger.debug("MCP '%s' non-JSON line: %s", self.name, text)
                continue
        if "error" in response:
            raise RuntimeError(f"MCP error from '{self.name}': {response['error']}")
        return response.get("result", {})

    async def _sse_rpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._http:
            raise RuntimeError(f"MCP HTTP client '{self.name}' is not connected")
        r = await self._http.post("/rpc", json=payload)
        r.raise_for_status()
        response = r.json()
        if "error" in response:
            raise RuntimeError(f"MCP error from '{self.name}': {response['error']}")
        return response.get("result", {})
