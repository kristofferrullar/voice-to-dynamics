"""Voice to Dynamics — management UI + channel webhook server.

Run from voice-to-dynamics/:
  .venv/bin/uvicorn ui.app:app --port 8080

Endpoints — Session management:
  GET  /          → serve UI
  GET  /status    → pipeline state, language, MCP servers
  POST /start     → start voice session subprocess
  POST /stop      → stop voice session
  POST /pause     → pause (SIGSTOP)
  POST /resume    → resume (SIGCONT)
  GET  /logs      → SSE stream of process output
  POST /language  → switch STT/TTS language
  POST /text      → process a text utterance through the agent (no mic)

Endpoints — Config:
  GET  /config          → read all pipeline + agent config
  POST /config          → write pipeline + agent config
  GET  /config/mcp      → list MCP servers
  POST /config/mcp      → enable / disable a named MCP server
  GET  /config/channels → read channel credentials status (no secrets)
  GET  /config/credentials  → credential status (no secret values)
  POST /config/credentials  → update .env values and reload

Endpoints — Channel webhooks:
  POST /webhook/teams          → Microsoft Teams Bot Framework
  POST /webhook/whatsapp       → Twilio WhatsApp
  POST /webhook/telegram       → Telegram Bot (webhook mode)
  POST /webhook/acs/call       → ACS incoming call (answer)
  POST /webhook/acs/events     → ACS mid-call events (recognize / play)

Endpoints — Agents:
  GET  /agents/patterns        → list available agent patterns
  GET  /agents                 → list all agent definitions
  POST /agents                 → create a new agent
  GET  /agents/{id}            → get a single agent
  PATCH /agents/{id}           → update agent config
  DELETE /agents/{id}          → delete agent
  POST /agents/{id}/start      → mark agent as running
  POST /agents/{id}/stop       → mark agent as stopped

Endpoints — MCP introspection:
  GET  /mcp/tools              → live tool list from all enabled MCP servers
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import httpx
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]          # voice-to-dynamics/
sys.path.insert(0, str(ROOT))

PIPELINE_YAML = ROOT / "config" / "pipeline.yaml"
MCP_YAML      = ROOT / "config" / "mcp_servers.yaml"
PYTHON        = ROOT / ".venv" / "bin" / "python3"
SCRIPT        = ROOT / "scripts" / "run_voice_session.py"

LANGUAGE_VOICES: dict[str, str] = {
    "en-US": "en-US-AriaNeural",
    "sv-SE": "sv-SE-MattiasNeural",
}

logger = logging.getLogger(__name__)

# ── global state ───────────────────────────────────────────────────────────────
_proc:   asyncio.subprocess.Process | None = None
_status: str = "stopped"          # stopped | running | paused

# deque gives O(1) append and O(1) left-truncation vs O(n) del list[0]
_log_lines: deque[str] = deque(maxlen=300)

# set gives O(1) add/discard vs O(n) list.remove
_log_queues: set[asyncio.Queue[str]] = set()

# Per-agent log state (keyed by agent_id)
_agent_log_lines: dict[str, deque] = {}
_agent_log_queues: dict[str, set[asyncio.Queue[str]]] = {}

# Active ACS call state: call_connection_id → {language, caller}
_acs_calls: dict[str, dict[str, Any]] = {}

# ── helpers ────────────────────────────────────────────────────────────────────

def _load_pipeline() -> dict[str, Any]:
    return yaml.safe_load(PIPELINE_YAML.read_text())

def _save_pipeline(cfg: dict[str, Any]) -> None:
    PIPELINE_YAML.write_text(yaml.dump(cfg, allow_unicode=True, default_flow_style=False))

def _load_mcp() -> dict[str, Any]:
    return yaml.safe_load(MCP_YAML.read_text())

def _save_mcp(cfg: dict[str, Any]) -> None:
    MCP_YAML.write_text(yaml.dump(cfg, allow_unicode=True, default_flow_style=False))

def _push_log(line: str) -> None:
    _log_lines.append(line)
    for q in _log_queues:
        q.put_nowait(line)

def _push_agent_log(agent_id: str, line: str) -> None:
    """Push to global log AND to the per-agent queue for the detail page."""
    _push_log(f"[{agent_id}] {line}")
    if agent_id not in _agent_log_lines:
        _agent_log_lines[agent_id] = deque(maxlen=300)
    _agent_log_lines[agent_id].append(line)
    for q in _agent_log_queues.get(agent_id, set()):
        q.put_nowait(line)

async def _drain_stream(stream: asyncio.StreamReader | None) -> None:
    if stream is None:
        return
    async for raw in stream:
        _push_log(raw.decode(errors="replace").rstrip())

async def _watch(proc: asyncio.subprocess.Process) -> None:
    global _status, _proc
    await asyncio.gather(_drain_stream(proc.stdout), _drain_stream(proc.stderr))
    await proc.wait()
    _status = "stopped"
    _proc   = None
    _push_log("■ Voice session ended")

def _parse_acs_endpoint(connection_string: str) -> str:
    """Extract the HTTPS endpoint URL from an ACS connection string."""
    for part in connection_string.split(";"):
        if part.lower().startswith("endpoint="):
            return part[9:].rstrip("/")
    return ""

def _get_settings():
    from config.settings import get_settings  # noqa: PLC0415
    return get_settings()

# ── app ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Voice to Dynamics UI")

from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)

@app.on_event("startup")
async def _startup() -> None:
    """On startup: restore running agents and start Telegram polling if configured."""
    from src.agent.router import agent_router  # noqa: PLC0415
    agent_router.set_log_fn(_push_agent_log)
    await agent_router.restore_running_agents()

    s = _get_settings()
    if s.telegram_bot_token:
        from src.channels.telegram import get_poller  # noqa: PLC0415
        get_poller(s.telegram_bot_token).start()
        logger.info("Telegram poller started (token configured)")


@app.on_event("shutdown")
async def _shutdown() -> None:
    """On shutdown: stop all running agents cleanly."""
    from src.agent.router import agent_router  # noqa: PLC0415
    await agent_router.close_all()

# ── Status ─────────────────────────────────────────────────────────────────────

@app.get("/status")
async def get_status() -> dict[str, Any]:
    cfg     = _load_pipeline()
    mcp_cfg = _load_mcp()
    return {
        "status":   _status,
        "language": cfg["stt"]["language"],
        "voice":    cfg["tts"]["voice"],
        "mcp_servers": [
            {
                "name":        s["name"],
                "enabled":     s.get("enabled", True),
                "description": s.get("description", ""),
            }
            for s in mcp_cfg.get("servers", [])
        ],
    }


# ── Session controls ────────────────────────────────────────────────────────────

@app.post("/start")
async def start_session() -> dict[str, Any]:
    global _proc, _status
    if _status == "running":
        return {"ok": True, "msg": "Already running"}

    # Ensure at least one agent with "local" channel is running
    from src.agent.router import agent_router   # noqa: PLC0415
    from src.agent.store import list_agents     # noqa: PLC0415
    local_agents = [a for a in list_agents() if "local" in a.get("channels", [])]
    running_local = [a for a in local_agents if agent_router.is_running(a["id"])]
    if not running_local and local_agents:
        try:
            await agent_router.start_agent(local_agents[0]["id"])
            _push_agent_log(local_agents[0]["id"], f"▶ Agent started: {local_agents[0]['name']}")
            _push_log(f"▶ Auto-started agent '{local_agents[0]['name']}' for local channel")
        except Exception as exc:
            _push_log(f"⚠️ Could not auto-start local agent: {exc}")
    elif not local_agents:
        _push_log("⚠️ No agent configured for the local channel — voice will use fallback")

    _push_log("▶ Starting voice session…")
    _proc = await asyncio.create_subprocess_exec(
        str(PYTHON), str(SCRIPT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(ROOT),
    )
    _status = "running"
    asyncio.create_task(_watch(_proc))
    return {"ok": True}


@app.post("/stop")
async def stop_session() -> dict[str, Any]:
    global _proc, _status
    if _proc:
        _proc.terminate()
        _push_log("■ Stopping voice session…")
    _status = "stopped"
    return {"ok": True}


@app.post("/pause")
async def pause_session() -> dict[str, Any]:
    global _status
    if _proc and _status == "running":
        os.kill(_proc.pid, signal.SIGSTOP)
        _status = "paused"
        _push_log("⏸ Voice session paused")
    return {"ok": True, "status": _status}


@app.post("/resume")
async def resume_session() -> dict[str, Any]:
    global _status
    if _proc and _status == "paused":
        os.kill(_proc.pid, signal.SIGCONT)
        _status = "running"
        _push_log("▶ Voice session resumed")
    return {"ok": True, "status": _status}


@app.get("/logs")
async def log_stream(agent_id: str | None = None) -> StreamingResponse:
    """Server-Sent Events stream. Pass ?agent_id=xxx for per-agent filtering."""
    q: asyncio.Queue[str] = asyncio.Queue()

    if agent_id:
        if agent_id not in _agent_log_queues:
            _agent_log_queues[agent_id] = set()
        _agent_log_queues[agent_id].add(q)
        history = list(_agent_log_lines.get(agent_id, deque()))[-80:]
    else:
        _log_queues.add(q)
        history = list(_log_lines)[-80:]

    async def generate():
        for line in history:
            yield f"data: {json.dumps(line)}\n\n"
        try:
            while True:
                try:
                    line = await asyncio.wait_for(q.get(), timeout=25)
                    yield f"data: {json.dumps(line)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if agent_id:
                _agent_log_queues.get(agent_id, set()).discard(q)
            else:
                _log_queues.discard(q)

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Language ────────────────────────────────────────────────────────────────────

class LanguageRequest(BaseModel):
    language: str  # "en-US" | "sv-SE"

@app.post("/language")
async def set_language(req: LanguageRequest) -> dict[str, Any]:
    if req.language not in LANGUAGE_VOICES:
        raise HTTPException(400, f"Unsupported language '{req.language}'. Use: {list(LANGUAGE_VOICES)}")
    cfg = _load_pipeline()
    cfg["stt"]["language"] = req.language
    cfg["tts"]["voice"]    = LANGUAGE_VOICES[req.language]
    cfg["stt"]["filler_word_removal"] = req.language == "sv-SE"
    _save_pipeline(cfg)
    _push_log(f"🌐 Language switched to {req.language} / voice: {LANGUAGE_VOICES[req.language]}")
    return {"ok": True, "language": req.language, "voice": LANGUAGE_VOICES[req.language]}


# ── Text input ──────────────────────────────────────────────────────────────────

class TextRequest(BaseModel):
    text: str

@app.post("/text")
async def process_text(req: TextRequest) -> dict[str, Any]:
    """Process a text utterance through the agent router (local channel)."""
    _push_log(f"💬 Text: {req.text}")
    try:
        from src.agent.router import agent_router  # noqa: PLC0415
        response = await agent_router.route("local", req.text, session_id="local_ui")
        _push_log(f"🤖 {response}")
        return {"ok": True, "response": response}
    except Exception as exc:
        _push_log(f"❌ Error: {exc}")
        raise HTTPException(500, str(exc)) from exc


# ── Config — pipeline ───────────────────────────────────────────────────────────

@app.get("/config")
async def get_config() -> dict[str, Any]:
    """Return the current pipeline config (safe to expose — no secrets)."""
    return _load_pipeline()


class PipelineConfigRequest(BaseModel):
    stt: dict[str, Any] | None = None
    tts: dict[str, Any] | None = None
    conversation_host: dict[str, Any] | None = None
    agent: dict[str, Any] | None = None


@app.post("/config")
async def save_config(req: PipelineConfigRequest) -> dict[str, Any]:
    """Merge-update pipeline.yaml. Only supplied keys are changed."""
    cfg = _load_pipeline()
    updates = req.model_dump(exclude_none=True)
    for section, values in updates.items():
        if section in cfg and isinstance(cfg[section], dict):
            cfg[section].update(values)
        else:
            cfg[section] = values
    _save_pipeline(cfg)
    _push_log("⚙️ Pipeline config updated")
    # Invalidate prompt cache and force agent reconnect on next message
    try:
        from src.agent.prompt_builder import invalidate_cache  # noqa: PLC0415
        invalidate_cache()
        from src.channels.handler import channel_handler      # noqa: PLC0415
        channel_handler.invalidate()
    except Exception:
        pass
    return {"ok": True, "config": cfg}


# ── Config — MCP servers ────────────────────────────────────────────────────────

@app.get("/config/mcp")
async def get_mcp_config() -> dict[str, Any]:
    cfg = _load_mcp()
    return {"servers": cfg.get("servers", [])}


class MCPToggleRequest(BaseModel):
    name: str
    enabled: bool

@app.post("/config/mcp")
async def toggle_mcp_server(req: MCPToggleRequest) -> dict[str, Any]:
    cfg = _load_mcp()
    found = False
    for srv in cfg.get("servers", []):
        if srv["name"] == req.name:
            srv["enabled"] = req.enabled
            found = True
            break
    if not found:
        raise HTTPException(404, f"MCP server '{req.name}' not found")
    _save_mcp(cfg)
    state = "enabled" if req.enabled else "disabled"
    _push_log(f"🔌 MCP server '{req.name}' {state}")
    try:
        from src.channels.handler import channel_handler  # noqa: PLC0415
        channel_handler.invalidate()
    except Exception:
        pass
    return {"ok": True, "name": req.name, "enabled": req.enabled}


# ── Config — channel credential status ─────────────────────────────────────────

@app.get("/config/channels")
async def get_channel_config() -> dict[str, Any]:
    """Return which channel credentials are configured (True/False — no secret values)."""
    s = _get_settings()
    return {
        "teams": {
            "configured": bool(s.teams_app_id and s.teams_app_password),
            "app_id":     s.teams_app_id or "",
        },
        "whatsapp": {
            "configured":   bool(s.twilio_account_sid and s.twilio_auth_token),
            "account_sid":  s.twilio_account_sid[:8] + "…" if s.twilio_account_sid else "",
            "phone_number": s.twilio_whatsapp_number or "",
        },
        "acs_voice": {
            "configured":   bool(s.acs_connection_string),
            "phone_number": s.acs_phone_number or "",
            "callback_url": s.acs_callback_url or "",
        },
        "telegram": {
            "configured": bool(s.telegram_bot_token),
            "mode":       "polling" if s.telegram_bot_token else "disabled",
        },
    }


# ── Config — credential management ─────────────────────────────────────────────

_ALLOWED_CREDENTIAL_KEYS = {
    "ANTHROPIC_API_KEY", "AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION",
    "GITHUB_PERSONAL_ACCESS_TOKEN", "AZURE_TENANT_ID", "AZURE_CLIENT_ID",
    "AZURE_CLIENT_SECRET", "DATAVERSE_ENVIRONMENT_URL", "TELEGRAM_BOT_TOKEN",
    "TEAMS_APP_ID", "TEAMS_APP_PASSWORD", "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_NUMBER",
}


@app.get("/config/credentials")
async def get_credentials() -> dict[str, Any]:
    """Return credential status — which are set (True/False) and safe partial previews. No full secret values."""
    s = _get_settings()

    def mask(v: str) -> str:
        return v[:4] + "…" if len(v) > 8 else ("set" if v else "")

    return {
        "credentials": [
            {"key": "ANTHROPIC_API_KEY",            "label": "Anthropic API Key",              "set": bool(s.anthropic_api_key),             "preview": mask(s.anthropic_api_key),           "description": "Claude LLM — required for agent", "group": "Core"},
            {"key": "AZURE_SPEECH_KEY",              "label": "Azure Speech Key",                "set": bool(s.azure_speech_key),              "preview": mask(s.azure_speech_key),            "description": "STT + TTS for voice messages", "group": "Core"},
            {"key": "AZURE_SPEECH_REGION",           "label": "Azure Speech Region",             "set": bool(s.azure_speech_region),           "preview": s.azure_speech_region,               "description": "e.g. swedencentral", "group": "Core"},
            {"key": "GITHUB_PERSONAL_ACCESS_TOKEN",  "label": "GitHub Token",                    "set": bool(s.github_personal_access_token),  "preview": mask(s.github_personal_access_token),"description": "GitHub MCP server — repo, issues, PRs", "group": "MCP Servers"},
            {"key": "AZURE_TENANT_ID",               "label": "Azure Tenant ID",                 "set": bool(s.azure_tenant_id),               "preview": mask(s.azure_tenant_id),             "description": "Dataverse / Dynamics 365", "group": "MCP Servers"},
            {"key": "AZURE_CLIENT_ID",               "label": "Azure Client ID",                 "set": bool(s.azure_client_id),               "preview": mask(s.azure_client_id),             "description": "Dataverse / Dynamics 365", "group": "MCP Servers"},
            {"key": "AZURE_CLIENT_SECRET",           "label": "Azure Client Secret",             "set": bool(s.azure_client_secret),           "preview": mask(s.azure_client_secret),         "description": "Dataverse / Dynamics 365", "group": "MCP Servers"},
            {"key": "DATAVERSE_ENVIRONMENT_URL",     "label": "Dataverse Environment URL",       "set": bool(s.dataverse_environment_url),     "preview": s.dataverse_environment_url[:30] + "…" if len(s.dataverse_environment_url) > 30 else s.dataverse_environment_url, "description": "e.g. https://org.crm.dynamics.com", "group": "MCP Servers"},
            {"key": "TELEGRAM_BOT_TOKEN",            "label": "Telegram Bot Token",              "set": bool(s.telegram_bot_token),            "preview": mask(s.telegram_bot_token),          "description": "From @BotFather — enables Telegram channel", "group": "Channels"},
            {"key": "TEAMS_APP_ID",                  "label": "Teams App ID",                    "set": bool(s.teams_app_id),                  "preview": mask(s.teams_app_id),                "description": "Azure Bot registration App ID", "group": "Channels"},
            {"key": "TEAMS_APP_PASSWORD",            "label": "Teams App Password",              "set": bool(s.teams_app_password),            "preview": mask(s.teams_app_password),          "description": "Azure Bot registration secret", "group": "Channels"},
            {"key": "TWILIO_ACCOUNT_SID",            "label": "Twilio Account SID",              "set": bool(s.twilio_account_sid),            "preview": mask(s.twilio_account_sid),          "description": "WhatsApp via Twilio", "group": "Channels"},
            {"key": "TWILIO_AUTH_TOKEN",             "label": "Twilio Auth Token",               "set": bool(s.twilio_auth_token),             "preview": mask(s.twilio_auth_token),           "description": "WhatsApp via Twilio", "group": "Channels"},
            {"key": "TWILIO_WHATSAPP_NUMBER",        "label": "Twilio WhatsApp Number",          "set": bool(s.twilio_whatsapp_number),        "preview": s.twilio_whatsapp_number,            "description": "e.g. whatsapp:+14155238886", "group": "Channels"},
        ]
    }


class CredentialUpdateRequest(BaseModel):
    updates: dict[str, str]


@app.post("/config/credentials")
async def update_credentials(req: CredentialUpdateRequest) -> dict[str, Any]:
    """Write new credential values to .env and reload settings cache."""
    unknown = set(req.updates) - _ALLOWED_CREDENTIAL_KEYS
    if unknown:
        raise HTTPException(400, f"Unknown credential keys: {unknown}")

    env_path = ROOT / ".env"
    env_text = env_path.read_text() if env_path.exists() else ""

    for key, value in req.updates.items():
        import re  # noqa: PLC0415
        pattern = re.compile(rf"^({re.escape(key)}=).*$", re.MULTILINE)
        if pattern.search(env_text):
            env_text = pattern.sub(rf"\g<1>{value}", env_text)
        else:
            env_text = env_text.rstrip() + f"\n{key}={value}\n"

    env_path.write_text(env_text)

    # Reload settings cache
    try:
        from config.settings import get_settings  # noqa: PLC0415
        get_settings.cache_clear()
        from src.channels.handler import channel_handler  # noqa: PLC0415
        channel_handler.invalidate()
    except Exception:
        pass

    updated_keys = list(req.updates.keys())
    _push_log(f"🔑 Credentials updated: {', '.join(updated_keys)}")
    return {"ok": True, "updated": updated_keys}


# ── Agent patterns ──────────────────────────────────────────────────────────────

@app.get("/api/agents/patterns")
async def get_patterns() -> dict[str, Any]:
    """Return all available agent patterns."""
    from src.agent.patterns import patterns_as_dicts  # noqa: PLC0415
    return {"patterns": patterns_as_dicts()}


# ── Agent CRUD ──────────────────────────────────────────────────────────────────

class AgentCreateRequest(BaseModel):
    name: str
    pattern: str = "voice_assistant"
    model: str = "claude-sonnet-4-6"
    mcp_servers: list[str] = []
    channels: list[str] = []
    memory: dict[str, Any] = {"enabled": True, "max_turns": 10}
    system_prompt_override: str | None = None


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    pattern: str | None = None
    model: str | None = None
    mcp_servers: list[str] | None = None
    channels: list[str] | None = None
    memory: dict[str, Any] | None = None
    system_prompt_override: str | None = None


@app.get("/api/agents")
async def list_agents() -> dict[str, Any]:
    from src.agent.store import list_agents as _list  # noqa: PLC0415
    return {"agents": _list()}


@app.post("/api/agents", status_code=201)
async def create_agent(req: AgentCreateRequest) -> dict[str, Any]:
    from src.agent.store import create_agent as _create  # noqa: PLC0415
    agent = _create(req.model_dump())
    _push_log(f"🤖 Agent created: {agent['name']} ({agent['id']})")
    return agent


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str) -> dict[str, Any]:
    from src.agent.store import get_agent as _get  # noqa: PLC0415
    agent = _get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    return agent


@app.patch("/api/agents/{agent_id}")
async def update_agent(agent_id: str, req: AgentUpdateRequest) -> dict[str, Any]:
    from src.agent.store import update_agent as _update  # noqa: PLC0415
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    agent = _update(agent_id, updates)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    _push_log(f"✏️ Agent updated: {agent['name']} ({agent_id})")
    return agent


@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str) -> dict[str, Any]:
    if agent_id == "default":
        raise HTTPException(400, "Cannot delete the default agent")
    from src.agent.store import delete_agent as _delete  # noqa: PLC0415
    if not _delete(agent_id):
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    _push_log(f"🗑️ Agent deleted: {agent_id}")
    return {"ok": True, "id": agent_id}


@app.post("/api/agents/{agent_id}/start")
async def start_agent(agent_id: str) -> dict[str, Any]:
    from src.agent.store import get_agent as _get  # noqa: PLC0415
    from src.agent.router import agent_router       # noqa: PLC0415
    agent = _get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    try:
        await agent_router.start_agent(agent_id)
    except Exception as exc:
        raise HTTPException(500, f"Failed to start agent: {exc}") from exc
    _push_log(f"▶ Agent started: {agent['name']} ({agent_id})")
    _push_agent_log(agent_id, f"▶ Agent started: {agent['name']}")
    return {"ok": True, "id": agent_id, "status": "running"}


@app.post("/api/agents/{agent_id}/stop")
async def stop_agent(agent_id: str) -> dict[str, Any]:
    from src.agent.store import get_agent as _get  # noqa: PLC0415
    from src.agent.router import agent_router       # noqa: PLC0415
    agent = _get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    await agent_router.stop_agent(agent_id)
    _push_log(f"■ Agent stopped: {agent['name']} ({agent_id})")
    _push_agent_log(agent_id, f"■ Agent stopped: {agent['name']}")
    return {"ok": True, "id": agent_id, "status": "stopped"}


# ── MCP — live tool introspection ───────────────────────────────────────────────

@app.get("/api/mcp/tools")
async def get_mcp_tools() -> dict[str, Any]:
    """Connect to all enabled MCP servers and return their full tool list.

    This is used by the agent setup wizard to show available tools when
    selecting which MCP servers to attach to an agent.
    Connects fresh each time so the list reflects the current server state.
    """
    from src.mcp.registry import MCPRegistry  # noqa: PLC0415

    registry = MCPRegistry()
    try:
        await registry.connect_all()
        raw_tools = await registry.get_tools()
        summaries = registry.get_server_summaries()

        # Group tools by server for the UI
        server_tools: dict[str, list[dict[str, Any]]] = {s["name"]: [] for s in summaries}
        for tool in raw_tools:
            # tool name format: "server_name__tool_name" OR just "tool_name"
            # match via server summaries
            for srv in summaries:
                if tool["name"] in srv["tools"]:
                    server_tools[srv["name"]].append({
                        "name":        tool["name"],
                        "description": tool.get("description", ""),
                        "parameters":  tool.get("inputSchema", {}),
                    })
                    break

        return {
            "servers": [
                {
                    "name":        srv["name"],
                    "description": srv["description"],
                    "tool_count":  len(srv["tools"]),
                    "tools":       server_tools.get(srv["name"], []),
                }
                for srv in summaries
            ]
        }
    finally:
        await registry.disconnect_all()


# ── Webhook — Microsoft Teams ────────────────────────────────────────────────────

@app.post("/webhook/teams")
async def teams_webhook(request: Request) -> dict[str, Any]:
    from src.channels import teams as teams_adapter   # noqa: PLC0415
    from src.channels.handler import channel_handler  # noqa: PLC0415

    s    = _get_settings()
    auth = request.headers.get("Authorization")

    if not await teams_adapter.verify_request(auth, s.teams_app_id):
        _push_log("⚠️ Teams: rejected request (bad JWT)")
        raise HTTPException(401, "Unauthorized")

    body: dict[str, Any] = await request.json()
    if body.get("type") != "message":
        return {"ok": True}  # Acknowledge non-message activities silently

    text = body.get("text", "").strip()
    if not text:
        return {"ok": True}

    service_url     = body.get("serviceUrl", "")
    conversation_id = body.get("conversation", {}).get("id", "")
    reply_to_id     = body.get("id", "")
    from_name       = body.get("from", {}).get("name", "someone")

    _push_log(f"📨 Teams [{from_name}]: {text}")
    reply_text = await channel_handler.process(text)
    _push_log(f"🤖 Teams reply: {reply_text}")

    if service_url and conversation_id and reply_to_id:
        await teams_adapter.send_reply(
            service_url     = service_url,
            conversation_id = conversation_id,
            reply_to_id     = reply_to_id,
            text            = reply_text,
            app_id          = s.teams_app_id,
            app_password    = s.teams_app_password,
        )
    return {"ok": True}


# ── Webhook — Twilio WhatsApp ────────────────────────────────────────────────────

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request) -> PlainTextResponse:
    from src.channels import whatsapp as wa_adapter   # noqa: PLC0415
    from src.channels.handler import channel_handler  # noqa: PLC0415

    s = _get_settings()

    form_bytes = await request.body()
    raw  = parse_qs(form_bytes.decode(), keep_blank_values=True)
    form: dict[str, str] = {k: v[0] for k, v in raw.items()}

    # Always verify when credentials are present; reject if verification fails
    sig = request.headers.get("X-Twilio-Signature")
    if s.twilio_auth_token:
        if not wa_adapter.verify_request(s.twilio_auth_token, str(request.url), form, sig):
            _push_log("⚠️ WhatsApp: rejected request (bad signature)")
            raise HTTPException(403, "Forbidden")

    msg  = wa_adapter.parse_incoming(form)
    text = msg["body"]
    if not text:
        return PlainTextResponse(wa_adapter.twiml_empty(), media_type="text/xml")

    from_number = msg["from_number"]
    _push_log(f"📱 WhatsApp [{from_number}]: {text}")
    reply_text = await channel_handler.process(text)
    _push_log(f"🤖 WhatsApp reply: {reply_text}")

    return PlainTextResponse(wa_adapter.twiml_message(reply_text), media_type="text/xml")


# ── Webhook — Telegram ───────────────────────────────────────────────────────────

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> dict[str, Any]:
    """Receive updates from Telegram (webhook mode — requires a public URL).

    In local development use polling mode instead: just set TELEGRAM_BOT_TOKEN
    and the poller starts automatically on server startup — no tunnel needed.
    """
    from src.channels import telegram as tg_adapter  # noqa: PLC0415

    s = _get_settings()
    if not s.telegram_bot_token:
        raise HTTPException(503, "Telegram not configured — set TELEGRAM_BOT_TOKEN")

    body: dict[str, Any] = await request.json()
    parsed = tg_adapter.parse_update(body)
    if parsed:
        _push_log(f"📩 Telegram [{parsed['user']}]: {parsed['text']}")
    await tg_adapter.handle_webhook(s.telegram_bot_token, body)
    return {"ok": True}


# ── Webhook — ACS incoming call ──────────────────────────────────────────────────

@app.post("/webhook/acs/call")
async def acs_incoming_call(request: Request) -> dict[str, Any]:
    """Receive IncomingCall cloud event from ACS and answer the call."""
    from src.channels import voice_acs as acs  # noqa: PLC0415

    s    = _get_settings()
    body = await request.json()

    # ACS sends an array of cloud events (or a single dict)
    events = body if isinstance(body, list) else [body]

    for event in events:
        # EventGrid subscription validation handshake
        if event.get("eventType") == "Microsoft.EventGrid.SubscriptionValidationEvent":
            code = event.get("data", {}).get("validationCode", "")
            return {"validationResponse": code}

        event_type, data = acs.parse_cloud_event(event)
        if event_type != acs.EVENT_INCOMING_CALL:
            continue

        incoming_ctx = data.get("incomingCallContext", "")
        caller       = data.get("from", {}).get("rawId", "unknown")
        _push_log(f"📞 ACS: incoming call from {caller}")

        acs_endpoint = _parse_acs_endpoint(s.acs_connection_string)
        if not acs_endpoint:
            _push_log("❌ ACS: no endpoint in ACS_CONNECTION_STRING")
            return {"ok": False}

        callback_url = s.acs_callback_url.rstrip("/") + "/webhook/acs/events"
        answer_body  = acs.build_answer_request(incoming_ctx, callback_url)

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{acs_endpoint}/calling/callConnections:answer?api-version=2024-06-15-preview",
                json=answer_body,
                headers={"Content-Type": "application/json"},
            )
        if resp.status_code not in (200, 201, 202):
            _push_log(f"❌ ACS answer failed {resp.status_code}: {resp.text[:200]}")
        else:
            call_id = resp.json().get("callConnectionId", "")
            _acs_calls[call_id] = {"language": "en-US", "caller": caller}
            _push_log(f"✅ ACS: call answered, connection id={call_id}")

    return {"ok": True}


# ── Webhook — ACS mid-call events ───────────────────────────────────────────────

@app.post("/webhook/acs/events")
async def acs_call_events(request: Request) -> dict[str, Any]:
    """Handle mid-call ACS events: play greeting, recognize speech, respond."""
    from src.channels import voice_acs as acs             # noqa: PLC0415
    from src.channels.handler import channel_handler      # noqa: PLC0415

    s    = _get_settings()
    body = await request.json()
    events = body if isinstance(body, list) else [body]

    acs_endpoint = _parse_acs_endpoint(s.acs_connection_string)

    async def _acs_post(path: str, payload: dict[str, Any]) -> None:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(
                f"{acs_endpoint}{path}",
                json=payload,
                headers={"Content-Type": "application/json"},
            )

    async def _play(call_id: str, text: str, op_ctx: str = "reply") -> None:
        lang  = _acs_calls.get(call_id, {}).get("language", "en-US")
        voice = LANGUAGE_VOICES.get(lang, "en-US-AriaNeural")
        await _acs_post(
            f"/calling/callConnections/{call_id}:play?api-version=2024-06-15-preview",
            acs.build_play_tts_request(text, voice_name=voice, operation_context=op_ctx),
        )

    async def _recognize(call_id: str, prompt: str) -> None:
        lang  = _acs_calls.get(call_id, {}).get("language", "en-US")
        voice = LANGUAGE_VOICES.get(lang, "en-US-AriaNeural")
        await _acs_post(
            f"/calling/callConnections/{call_id}:startRecognizing?api-version=2024-06-15-preview",
            acs.build_recognize_request(prompt, voice_name=voice, speech_language=lang),
        )

    async def _hangup(call_id: str) -> None:
        await _acs_post(
            f"/calling/callConnections/{call_id}:hangUp?api-version=2024-06-15-preview",
            acs.build_hangup_request(),
        )

    for event in events:
        event_type, data = acs.parse_cloud_event(event)
        call_id = data.get("callConnectionId", "")

        if event_type == acs.EVENT_CALL_CONNECTED:
            _push_log(f"📞 ACS: call connected {call_id}")
            if acs_endpoint:
                await _recognize(call_id, acs.GREETING_TEXT)

        elif event_type == acs.EVENT_RECOGNIZE_COMPLETED:
            speech_text = acs.extract_speech_result(data)
            _push_log(f"🎤 ACS [{call_id}]: \"{speech_text}\"")
            if speech_text and acs_endpoint:
                reply = await channel_handler.process(speech_text)
                _push_log(f"🤖 ACS reply: {reply}")
                await _play(call_id, reply, op_ctx="agent_reply")

        elif event_type == acs.EVENT_RECOGNIZE_FAILED:
            _push_log(f"⚠️ ACS: recognize failed for {call_id}")
            if acs_endpoint:
                await _play(call_id, "Sorry, I didn't catch that. Could you repeat that?", op_ctx="retry")

        elif event_type == acs.EVENT_PLAY_COMPLETED:
            op_ctx = data.get("operationContext", "")
            if op_ctx == "agent_reply" and acs_endpoint:
                await _recognize(call_id, "Is there anything else I can help you with?")
            elif op_ctx == "retry" and acs_endpoint:
                await _recognize(call_id, "")

        elif event_type == acs.EVENT_CALL_DISCONNECTED:
            _push_log(f"📞 ACS: call disconnected {call_id}")
            _acs_calls.pop(call_id, None)

    return {"ok": True}


# ── Static assets (SvelteKit build) ────────────────────────────────────────────
_static_dir = Path(__file__).parent / "static"
if (_static_dir / "_app").exists():
    app.mount("/_app", StaticFiles(directory=str(_static_dir / "_app")), name="app-assets")


# ── SPA catch-all — serves index.html for all unmatched routes (client-side nav) ──
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str) -> Response:
    index = _static_dir / "index.html"
    if index.exists():
        return Response(content=index.read_bytes(), media_type="text/html")
    return Response(content="UI not built. Run: cd frontend && npm run build", status_code=404)
