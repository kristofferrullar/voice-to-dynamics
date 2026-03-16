# voice-to-dynamics

A voice assistant that connects to **any MCP server** — Microsoft Dataverse / Dynamics 365, GitHub, or your own — and lets people interact through voice, text, Microsoft Teams, or WhatsApp.

Built with [Azure Cognitive Services](https://azure.microsoft.com/en-us/products/ai-services/ai-speech) (STT/TTS), [Anthropic Claude](https://www.anthropic.com) (agent + conversation host), and the [Model Context Protocol](https://modelcontextprotocol.io).

---

## Features

- 🎤 **Voice pipeline** — Azure Speech STT → parallel(conversation host + agent) → Azure Speech TTS
- 🤖 **Generic MCP agent** — connects to any stdio or SSE MCP server; auto-discovers tools
- 🧠 **Conversation memory** — retains context across turns; configurable depth
- 💬 **Microsoft Teams** — text bot via Azure Bot Service (JWT-verified)
- 📱 **WhatsApp** — text bot via Twilio (signature-verified, TwiML)
- 📞 **Voice calls** — inbound PSTN/VoIP via Azure Communication Services
- 🖥️ **Management UI** — Start/Stop/Pause, live logs, config editor, channel status (localhost:8080)
- 🔌 **Dataverse MCP server** — built-in server for Dynamics 365 (query, create, update, count)
- 🐙 **GitHub MCP server** — wired via `@modelcontextprotocol/server-github`

---

## Quick start

### 1. Prerequisites

- Python 3.11+
- Node.js 18+ (for GitHub MCP server)
- [uv](https://docs.astral.sh/uv/) — `pip install uv`

### 2. Install

```bash
git clone https://github.com/<your-org>/voice-to-dynamics.git
cd voice-to-dynamics
uv sync
```

### 3. Configure credentials

```bash
cp .env.example .env
# Edit .env and fill in your values — see notes below
```

Minimum required to run the text agent (no microphone):

```env
ANTHROPIC_API_KEY=sk-ant-...
```

For voice (STT/TTS):

```env
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=swedencentral
```

### 4. Start the UI

```bash
.venv/bin/uvicorn ui.app:app --port 8080
```

Open [http://localhost:8080](http://localhost:8080) — use the **Text Input** box to talk to the agent without a microphone, or press **Start** to begin a voice session.

---

## Adding MCP servers

Edit `config/mcp_servers.yaml` — the agent auto-discovers all tools on startup:

```yaml
servers:
  - name: my-server
    enabled: true
    transport: stdio                          # or "sse"
    command: ["npx", "-y", "@my/mcp-server"]
    description: "My service — what it does"
```

See [`docs/adding_mcp_server.md`](docs/adding_mcp_server.md) for a step-by-step guide.

---

## Architecture

```
Microphone
    │
    ▼
Azure Speech STT
    │  utterance
    ├──────────────────────────────────┐
    ▼                                  ▼
ConversationHost              MCPAgent (Claude Sonnet)
(Claude Haiku)                    │
Speaks acknowledgement            ├── MCPRegistry
immediately (~300 ms)             │     ├── dataverse MCP server (stdio)
                                  │     ├── github MCP server   (stdio)
                                  │     └── your MCP server     (stdio/sse)
                                  │
                                  ▼
                            final response
                                  │
                                  ▼
                          Azure Speech TTS
                                  │
                                  ▼
                              Speaker
```

Channels (Teams, WhatsApp, ACS voice) share the same `MCPAgent` via a singleton `ChannelHandler`, so MCP connections are established once and reused across all incoming messages.

Full architecture: [`docs/architecture.md`](docs/architecture.md)

---

## Configuration

### `config/pipeline.yaml`

Controls STT, TTS, conversation host, and agent settings:

```yaml
stt:
  provider: azure
  language: en-US          # en-US | sv-SE
  silence_timeout_ms: 1500
  filler_word_removal: false

tts:
  provider: azure
  voice: en-US-AriaNeural

conversation_host:
  provider: claude          # claude | azure_realtime
  system_prompt: "..."

agent:
  provider: anthropic
  model: claude-sonnet-4-6
  max_tool_iterations: 10
  memory:
    enabled: true
    max_turns: 10
    reset_phrases: ["new session", "reset"]
```

All settings are editable live from the **Config** tab in the UI (no restart needed).

### `config/mcp_servers.yaml`

Registry of MCP servers. Enable/disable individual servers from the UI **Config** tab.

---

## Channels

### Microsoft Teams

1. Create an Azure Bot registration
2. Set the messaging endpoint to `https://<your-tunnel>/webhook/teams`
3. Add the Teams channel in Azure Portal
4. Set `TEAMS_APP_ID` + `TEAMS_APP_PASSWORD` in `.env`

### WhatsApp (Twilio)

1. Create a Twilio account and activate a WhatsApp number
2. Set the webhook URL to `https://<your-tunnel>/webhook/whatsapp`
3. Set `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` + `TWILIO_WHATSAPP_NUMBER` in `.env`

### Voice calls (Azure Communication Services)

1. Create an ACS resource and acquire a phone number
2. Register an Event Grid subscription for `IncomingCall` pointing to `https://<your-tunnel>/webhook/acs/call`
3. Set `ACS_CONNECTION_STRING` + `ACS_PHONE_NUMBER` + `ACS_CALLBACK_URL` in `.env`

Use [ngrok](https://ngrok.com) or [Azure Dev Tunnel](https://learn.microsoft.com/azure/developer/dev-tunnels/overview) to expose local webhooks during development.

---

## Development

```bash
# Run tests
uv run pytest

# Type-check
uv run mypy src/

# Start voice session directly (no UI)
uv run python scripts/run_voice_session.py

# Run Dataverse MCP server standalone (for testing)
uv run python scripts/run_mcp_server.py

# Discover Dataverse schema
uv run python scripts/discover_schema.py
```

---

## Built-in Dataverse MCP tools

| Tool | Description |
|---|---|
| `query_records_tool` | Fetch records with `$select`, `$filter`, `$orderby`, `$top` |
| `count_records_tool` | Count records matching an OData filter |
| `create_record_tool` | Create a new record (requires `create` permission) |
| `update_record_tool` | Update an existing record (requires `update` permission) |
| `delete_record_tool` | Delete a record — **disabled by default** (`ALLOW_DATAVERSE_DELETE=true`) |
| `get_current_user` | Resolve the authenticated service principal (for "my" queries) |

Allowed tables and column schemas are defined in `mcp_servers/dataverse/allowed_tables.yaml` and `schema/*.yaml`.

---

## License

MIT
