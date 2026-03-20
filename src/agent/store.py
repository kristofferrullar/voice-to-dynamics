"""Agent store — persistent CRUD for agent definitions.

Agents are stored in config/agents.json as a list of AgentConfig dicts.
All reads/writes go through this module so the rest of the codebase never
touches the file directly.

Thread safety: all public functions acquire _LOCK before touching the file.
The lock is a threading.Lock (not asyncio) because the store is called from
both the sync CLI and the async FastAPI app.
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from src.agent.patterns import VOICE_ASSISTANT, get_pattern

_AGENTS_PATH = Path(__file__).resolve().parents[2] / "config" / "agents.json"
_LOCK = threading.Lock()

# ── Schema ─────────────────────────────────────────────────────────────────────
# An AgentConfig is a plain dict that matches this shape:
#
# {
#   "id":                    str          # uuid4 slug or "default"
#   "name":                  str
#   "pattern":               str          # pattern id, e.g. "voice_assistant"
#   "model":                 str          # e.g. "claude-sonnet-4-6"
#   "mcp_servers":           list[str]    # [] = use all enabled servers
#   "channels":              list[str]    # e.g. ["telegram", "local"]
#   "memory":                dict         # {enabled, max_turns}
#   "system_prompt_override": str | null  # replaces pattern base_prompt when set
#   "status":                str          # "stopped" | "running" | "paused"
# }


# ── Default agent (seeded on first run) ────────────────────────────────────────

_DEFAULT_AGENT: dict[str, Any] = {
    "id": "default",
    "name": "Voice Assistant",
    "pattern": VOICE_ASSISTANT.id,
    "model": "claude-sonnet-4-6",
    "mcp_servers": [],
    "channels": ["telegram", "local"],
    "memory": {"enabled": True, "max_turns": 10},
    "system_prompt_override": None,
    "status": "stopped",
}


# ── File I/O ───────────────────────────────────────────────────────────────────

def _read() -> list[dict[str, Any]]:
    """Read agents from disk, seeding the default if the file doesn't exist."""
    if not _AGENTS_PATH.exists():
        _write([_DEFAULT_AGENT])
        return [_DEFAULT_AGENT]
    try:
        data = json.loads(_AGENTS_PATH.read_text())
        return data if isinstance(data, list) else [_DEFAULT_AGENT]
    except (json.JSONDecodeError, OSError):
        return [_DEFAULT_AGENT]


def _write(agents: list[dict[str, Any]]) -> None:
    _AGENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _AGENTS_PATH.write_text(json.dumps(agents, indent=2))


# ── Public API ─────────────────────────────────────────────────────────────────

def list_agents() -> list[dict[str, Any]]:
    """Return all agent configs."""
    with _LOCK:
        return _read()


def get_agent(agent_id: str) -> dict[str, Any] | None:
    """Return a single agent config by id, or None if not found."""
    with _LOCK:
        return next((a for a in _read() if a["id"] == agent_id), None)


def create_agent(data: dict[str, Any]) -> dict[str, Any]:
    """Create a new agent, generating an id if none is provided."""
    with _LOCK:
        agents = _read()
        agent: dict[str, Any] = {
            "id":                    data.get("id") or str(uuid.uuid4())[:8],
            "name":                  data.get("name", "New Agent"),
            "pattern":               data.get("pattern", VOICE_ASSISTANT.id),
            "model":                 data.get("model", "claude-sonnet-4-6"),
            "mcp_servers":           data.get("mcp_servers", []),
            "channels":              data.get("channels", []),
            "memory":                data.get("memory", {"enabled": True, "max_turns": 10}),
            "system_prompt_override": data.get("system_prompt_override"),
            "openclaw_url":          data.get("openclaw_url", "ws://openclaw-gateway:18789"),
            "openclaw_agent_id":     data.get("openclaw_agent_id", "voice-agent"),
            "status":                "stopped",
        }
        agents.append(agent)
        _write(agents)
        return agent


def update_agent(agent_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Partial-update an agent. Returns the updated agent, or None if not found."""
    # These fields must not be overwritten via a PATCH
    _IMMUTABLE = {"id", "status"}
    with _LOCK:
        agents = _read()
        for agent in agents:
            if agent["id"] == agent_id:
                for key, value in updates.items():
                    if key not in _IMMUTABLE:
                        agent[key] = value
                _write(agents)
                return agent
        return None


def delete_agent(agent_id: str) -> bool:
    """Delete an agent by id. Returns True if deleted, False if not found."""
    with _LOCK:
        agents = _read()
        filtered = [a for a in agents if a["id"] != agent_id]
        if len(filtered) == len(agents):
            return False
        _write(filtered)
        return True


def set_status(agent_id: str, status: str) -> dict[str, Any] | None:
    """Update only the status field of an agent."""
    with _LOCK:
        agents = _read()
        for agent in agents:
            if agent["id"] == agent_id:
                agent["status"] = status
                _write(agents)
                return agent
        return None


def build_system_prompt(agent: dict[str, Any], server_summaries: list[dict[str, Any]]) -> str:
    """Build the full system prompt for an agent.

    Uses system_prompt_override if set, otherwise fills the pattern's base_prompt
    template with a live tools section built from server_summaries.
    """
    if agent.get("system_prompt_override"):
        return agent["system_prompt_override"]

    pattern = get_pattern(agent.get("pattern", VOICE_ASSISTANT.id))

    # Build tools section inline (same logic as prompt_builder._build_servers_section)
    if not server_summaries:
        tools_section = (
            "No MCP servers are currently connected.\n"
            "Answer from your own knowledge, or let the user know no tools are available."
        )
    else:
        lines = ["You have access to the following services via MCP tools:\n"]
        for srv in server_summaries:
            header = f"  • {srv['name']}"
            if srv.get("description"):
                header += f": {srv['description']}"
            lines.append(header)
            tools = srv.get("tools", [])
            if tools:
                preview = ", ".join(tools[:5])
                if len(tools) > 5:
                    preview += f" … (+{len(tools) - 5} more)"
                lines.append(f"    Tools: {preview}")
        lines.append(
            "\nChoose whichever tools best match the user's request."
        )
        tools_section = "\n".join(lines)

    return pattern.base_prompt.replace("{tools_section}", tools_section)
