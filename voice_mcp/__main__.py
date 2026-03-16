"""voice-mcp CLI.

Usage:
    python -m voice_mcp               # show help
    python -m voice_mcp check         # verify credentials + MCP connections
    python -m voice_mcp setup         # interactive wizard to create / fill .env
    python -m voice_mcp run           # start the voice session
    python -m voice_mcp ui            # start the management UI on :8080
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ── Colour helpers ─────────────────────────────────────────────────────────────
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_RED    = "\033[31m"
_CYAN   = "\033[36m"
_DIM    = "\033[2m"

def _ok(msg: str)   -> str: return f"{_GREEN}✅ {msg}{_RESET}"
def _warn(msg: str) -> str: return f"{_YELLOW}⚠️  {msg}{_RESET}"
def _err(msg: str)  -> str: return f"{_RED}❌ {msg}{_RESET}"
def _skip(msg: str) -> str: return f"{_DIM}⚪ {msg}{_RESET}"
def _hdr(msg: str)  -> str: return f"\n{_BOLD}{_CYAN}{msg}{_RESET}"


# ── check ─────────────────────────────────────────────────────────────────────

async def _check() -> None:
    from voice_mcp import __version__
    print(f"{_BOLD}voice-mcp v{__version__} — connection check{_RESET}")
    print("─" * 50)

    from config.settings import Settings
    s = Settings()  # fresh (not cached) so .env changes are picked up

    # ── Credentials ────────────────────────────────────────────────────────────
    print(_hdr("Credentials"))

    def cred(label: str, value: str, note: str = "") -> None:
        suffix = f"  {_DIM}({note}){_RESET}" if note else ""
        if value:
            print(f"  {_ok(label)}{suffix}")
        else:
            print(f"  {_skip(label + ' — not set')}{suffix}")

    cred("ANTHROPIC_API_KEY",             s.anthropic_api_key)
    cred("AZURE_SPEECH_KEY",              s.azure_speech_key,
         f"region: {s.azure_speech_region}")
    cred("AZURE_OPENAI_API_KEY",          s.azure_openai_api_key,
         "for realtime host (optional)")
    cred("GITHUB_PERSONAL_ACCESS_TOKEN",  s.github_personal_access_token)
    cred("AZURE_TENANT_ID",               s.azure_tenant_id,   "Dataverse")
    cred("AZURE_CLIENT_ID",               s.azure_client_id,   "Dataverse")
    cred("DATAVERSE_ENVIRONMENT_URL",     s.dataverse_environment_url)
    cred("TEAMS_APP_ID",                  s.teams_app_id)
    cred("TWILIO_ACCOUNT_SID",            s.twilio_account_sid)
    cred("TELEGRAM_BOT_TOKEN",            s.telegram_bot_token,  "from @BotFather")
    cred("ACS_CONNECTION_STRING",         s.acs_connection_string)

    # ── MCP servers ────────────────────────────────────────────────────────────
    print(_hdr("MCP Servers"))

    from src.mcp.registry import MCPRegistry
    registry = MCPRegistry()
    await registry.connect_all()
    summaries = registry.get_server_summaries()

    if not summaries:
        print(f"  {_warn('No MCP servers connected — check mcp_servers.yaml and credentials')}")
    else:
        for srv in summaries:
            name  = srv["name"]
            tools = srv.get("tools", [])
            preview = ", ".join(tools[:4]) + (f" … (+{len(tools)-4})" if len(tools) > 4 else "")
            print(f"  {_ok(name + f'  ({len(tools)} tools)')}")
            if preview:
                print(f"      {_DIM}{preview}{_RESET}")

    await registry.disconnect_all()

    # ── Channels ───────────────────────────────────────────────────────────────
    print(_hdr("Channels"))

    def channel(name: str, configured: bool, note: str = "") -> None:
        suffix = f"  {_DIM}{note}{_RESET}" if note else ""
        if configured:
            print(f"  {_ok(name)}{suffix}")
        else:
            print(f"  {_skip(name + ' — not configured')}{suffix}")

    channel("Microsoft Teams",  bool(s.teams_app_id and s.teams_app_password),
            "webhook: /webhook/teams")
    channel("WhatsApp (Twilio)", bool(s.twilio_account_sid and s.twilio_auth_token),
            "webhook: /webhook/whatsapp")
    channel("Telegram",          bool(s.telegram_bot_token),
            "polling (no tunnel needed)" if s.telegram_bot_token else "set TELEGRAM_BOT_TOKEN")
    channel("ACS Voice",         bool(s.acs_connection_string),
            "webhook: /webhook/acs/call")

    # ── Summary ────────────────────────────────────────────────────────────────
    print()
    n_servers  = len(summaries)
    n_channels = sum([
        bool(s.teams_app_id and s.teams_app_password),
        bool(s.twilio_account_sid and s.twilio_auth_token),
        bool(s.telegram_bot_token),
        bool(s.acs_connection_string),
    ])
    agent_ready = bool(s.anthropic_api_key)

    status_parts = []
    if agent_ready:
        status_parts.append(_ok(f"agent ready"))
    else:
        status_parts.append(_err("agent not ready — set ANTHROPIC_API_KEY"))
    status_parts.append(f"{n_servers} MCP server(s)")
    status_parts.append(f"{n_channels} channel(s) active")
    print("  " + " · ".join(status_parts))

    print()
    print(f"  {_DIM}Run 'python -m voice_mcp ui' to start the management UI on :8080{_RESET}")
    print(f"  {_DIM}Run 'python -m voice_mcp run' to start a voice session{_RESET}")


# ── setup ─────────────────────────────────────────────────────────────────────

def _setup() -> None:
    from voice_mcp import __version__
    print(f"{_BOLD}voice-mcp v{__version__} — setup wizard{_RESET}")
    print("─" * 50)

    env_path    = ROOT / ".env"
    example_path = ROOT / ".env.example"

    if not env_path.exists():
        if example_path.exists():
            shutil.copy(example_path, env_path)
            print(f"  Created .env from .env.example\n")
        else:
            env_path.touch()
            print(f"  Created empty .env\n")
    else:
        print(f"  .env already exists — updating values you provide\n")

    # Read current contents
    lines = env_path.read_text().splitlines()
    values: dict[str, str] = {}
    for line in lines:
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip()

    def ask(key: str, prompt: str, current: str = "", secret: bool = False) -> str:
        display = ("*" * 8) if (secret and current) else (current or "not set")
        raw = input(f"  {prompt}\n  [{display}]: ").strip()
        return raw if raw else current

    def section(title: str) -> None:
        print(f"\n{_BOLD}{title}{_RESET}")

    section("1/5  Anthropic (agent LLM)")
    values["ANTHROPIC_API_KEY"] = ask(
        "ANTHROPIC_API_KEY",
        "Anthropic API key — https://console.anthropic.com",
        values.get("ANTHROPIC_API_KEY", ""),
        secret=True,
    )

    section("2/5  Azure Speech (STT + TTS)")
    values["AZURE_SPEECH_KEY"] = ask(
        "AZURE_SPEECH_KEY",
        "Azure Speech key — portal.azure.com → Speech resource → Keys",
        values.get("AZURE_SPEECH_KEY", ""),
        secret=True,
    )
    values["AZURE_SPEECH_REGION"] = ask(
        "AZURE_SPEECH_REGION",
        "Azure Speech region (e.g. swedencentral, eastus)",
        values.get("AZURE_SPEECH_REGION", "swedencentral"),
    )

    section("3/5  GitHub MCP server (optional)")
    values["GITHUB_PERSONAL_ACCESS_TOKEN"] = ask(
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "GitHub PAT — https://github.com/settings/tokens  (scopes: repo, issues)",
        values.get("GITHUB_PERSONAL_ACCESS_TOKEN", ""),
        secret=True,
    )

    section("4/5  Microsoft Dataverse (optional)")
    print(f"  {_DIM}Leave blank to skip — Dataverse tools will be disabled{_RESET}")
    values["AZURE_TENANT_ID"]            = ask("AZURE_TENANT_ID",        "Azure Tenant ID",        values.get("AZURE_TENANT_ID", ""))
    values["AZURE_CLIENT_ID"]            = ask("AZURE_CLIENT_ID",        "App Registration Client ID", values.get("AZURE_CLIENT_ID", ""))
    values["AZURE_CLIENT_SECRET"]        = ask("AZURE_CLIENT_SECRET",    "Client Secret",          values.get("AZURE_CLIENT_SECRET", ""), secret=True)
    values["DATAVERSE_ENVIRONMENT_URL"]  = ask("DATAVERSE_ENVIRONMENT_URL", "Environment URL (e.g. https://org.crm4.dynamics.com)", values.get("DATAVERSE_ENVIRONMENT_URL", ""))

    section("5/5  Channels (optional — press Enter to skip each)")
    print(f"  {_DIM}Teams, WhatsApp, and ACS Voice are optional. You need a public HTTPS URL")
    print(f"  (ngrok / Azure Dev Tunnel) to receive webhooks.{_RESET}")
    values["TEAMS_APP_ID"]       = ask("TEAMS_APP_ID",       "Teams App ID",         values.get("TEAMS_APP_ID", ""))
    values["TEAMS_APP_PASSWORD"] = ask("TEAMS_APP_PASSWORD", "Teams App Password",   values.get("TEAMS_APP_PASSWORD", ""), secret=True)
    values["TWILIO_ACCOUNT_SID"] = ask("TWILIO_ACCOUNT_SID", "Twilio Account SID",   values.get("TWILIO_ACCOUNT_SID", ""))
    values["TWILIO_AUTH_TOKEN"]  = ask("TWILIO_AUTH_TOKEN",  "Twilio Auth Token",    values.get("TWILIO_AUTH_TOKEN", ""), secret=True)
    values["TWILIO_WHATSAPP_NUMBER"] = ask("TWILIO_WHATSAPP_NUMBER", "Twilio WhatsApp number (e.g. whatsapp:+14155238886)", values.get("TWILIO_WHATSAPP_NUMBER", ""))
    values["ACS_CONNECTION_STRING"] = ask("ACS_CONNECTION_STRING", "ACS Connection String", values.get("ACS_CONNECTION_STRING", ""), secret=True)
    values["ACS_PHONE_NUMBER"]   = ask("ACS_PHONE_NUMBER",   "ACS Phone Number",     values.get("ACS_PHONE_NUMBER", ""))
    values["ACS_CALLBACK_URL"]   = ask("ACS_CALLBACK_URL",   "ACS Callback URL (your public HTTPS base URL)", values.get("ACS_CALLBACK_URL", ""))

    # Re-write .env preserving comments and adding/updating values
    existing_keys = set()
    new_lines: list[str] = []
    for line in lines:
        if "=" in line and not line.startswith("#"):
            k = line.partition("=")[0].strip()
            existing_keys.add(k)
            new_lines.append(f"{k}={values.get(k, '')}")
        else:
            new_lines.append(line)
    # Append any keys that weren't already in the file
    for k, v in values.items():
        if k not in existing_keys and v:
            new_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(new_lines) + "\n")

    print(f"\n  {_ok('.env saved')}")
    print(f"\n  Run {_BOLD}python -m voice_mcp check{_RESET} to verify your setup.")


# ── run / ui ──────────────────────────────────────────────────────────────────

def _run_voice() -> None:
    python = ROOT / ".venv" / "bin" / "python3"
    script = ROOT / "scripts" / "run_voice_session.py"
    subprocess.run([str(python), str(script)], cwd=str(ROOT), check=False)


def _run_ui(port: int = 8080) -> None:
    uvicorn = ROOT / ".venv" / "bin" / "uvicorn"
    subprocess.run(
        [str(uvicorn), "ui.app:app", "--port", str(port)],
        cwd=str(ROOT),
        check=False,
    )


# ── entry point ───────────────────────────────────────────────────────────────

def _usage() -> None:
    from voice_mcp import __version__
    print(f"{_BOLD}voice-mcp v{__version__}{_RESET}  — generic voice agent for any MCP server")
    print()
    print("Commands:")
    print(f"  {_BOLD}check{_RESET}   Verify credentials and MCP server connections")
    print(f"  {_BOLD}setup{_RESET}   Interactive wizard to create / update .env")
    print(f"  {_BOLD}run{_RESET}     Start the voice session (microphone)")
    print(f"  {_BOLD}ui{_RESET}      Start the management UI on :8080")
    print()
    print(f"Example: {_DIM}python -m voice_mcp check{_RESET}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    match cmd:
        case "check":
            asyncio.run(_check())
        case "setup":
            _setup()
        case "run":
            _run_voice()
        case "ui":
            port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
            _run_ui(port)
        case _:
            _usage()


if __name__ == "__main__":
    main()
