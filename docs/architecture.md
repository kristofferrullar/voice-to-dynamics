# Architecture

## Overview

Voice-to-Dynamics is a local voice assistant that lets Swedish-speaking users interact with Microsoft Dataverse / Dynamics 365 through natural speech.

```
User Speech
    │
    ▼
[1] STT Provider (Azure Speech, sv-SE)
    │ + SwedishPreprocessor (filler word removal)
    ▼
[2a] Conversation Host                [2b] Agent (Claude Sonnet)
     Azure OpenAI Real-time                 Intent extraction
     "Söker nu..."                          │
    │                                       ▼
    ▼                                  MCP Registry
[3a] Spoken immediately (~300ms)            │
                                   ┌────────┴─────────┐
                                   │                  │
                              MCP Server 1       MCP Server 2 ...
                              (Dataverse)        (future)
                                   │
                                   ▼
                            Dataverse Web API
                                   │
                                   ▼
                            Agent result → TTS → User
```

## Components

### STT Provider (`src/providers/stt/`)
Azure Speech SDK with Swedish (`sv-SE`) continuous recognition. The `SwedishPreprocessor` strips hesitation sounds and filler words before text reaches the agent.

### Conversation Host (`src/providers/conversation/`)
Azure OpenAI Real-time API (WebSocket). Receives the cleaned utterance text, returns a brief spoken acknowledgement directly as PCM16 audio (~300 ms latency). The agent processes in parallel.

### Agent (`src/agent/`)
Claude Sonnet running a tool-use loop. System prompt assembled at startup from `schema/*.yaml` and `mcp_servers/dataverse/allowed_tables.yaml`. Uses the MCP registry to call Dataverse tools.

### MCP Registry (`src/mcp/`)
Reads `config/mcp_servers.yaml`, connects to all enabled servers, aggregates their tool lists, and routes tool calls to the correct server. Both stdio (subprocess) and SSE (HTTP) transports are supported.

### Dataverse MCP Server (`mcp_servers/dataverse/`)
FastMCP server exposing: `query_records_tool`, `count_records_tool`, `create_record_tool`, `update_record_tool`, `delete_record_tool` (disabled), `get_current_user`. Each tool validates table name and permissions against `allowed_tables.yaml` before calling the Dataverse Web API.

### TTS Provider (`src/providers/tts/`)
Azure Speech SDK TTS with Swedish voice (`sv-SE-MattiasNeural`). Used for the agent's final spoken result.

### Orchestrator (`src/orchestrator/pipeline.py`)
Wires all components. On each utterance, runs conversation host and agent as concurrent asyncio tasks.

---

## Modularity

Every provider and MCP server is configured, not hardcoded:

| What to change | Where |
|---|---|
| STT provider | `config/pipeline.yaml` → `stt.provider` |
| TTS provider | `config/pipeline.yaml` → `tts.provider` |
| Conversation host | `config/pipeline.yaml` → `conversation_host.provider` |
| Agent LLM | `config/pipeline.yaml` → `agent.provider` + `agent.model` |
| Add MCP server | `config/mcp_servers.yaml` → add entry, set `enabled: true` |

See `docs/adding_mcp_server.md` for how to add a new MCP server.

---

## Azure Setup

### 1. Register an Entra ID Application

1. Go to **Azure Portal** → **Entra ID** → **App registrations** → **New registration**
2. Name it (e.g. "voice-to-dynamics-app")
3. Note the **Application (client) ID** → `AZURE_CLIENT_ID`
4. Note the **Directory (tenant) ID** → `AZURE_TENANT_ID`
5. Under **Certificates & secrets** → create a **client secret** → `AZURE_CLIENT_SECRET`

### 2. Grant Dataverse Permission

1. In the app registration → **API permissions** → **Add a permission**
2. Select **Dynamics CRM** → **Application permissions** → `user_impersonation`
3. **Grant admin consent**

### 3. Create a Dataverse Application User

1. Go to **Power Platform Admin Center** → your environment → **Settings** → **Users** → **Application users**
2. **New app user** → select the registered app
3. Assign a **security role** (e.g. "Sales Person" or custom role with required table permissions)

### 4. Azure Speech

1. Create an **Azure Cognitive Services** (Speech) resource
2. Note the **key** → `AZURE_SPEECH_KEY` and **region** → `AZURE_SPEECH_REGION`

### 5. Azure OpenAI Real-time

1. Create an **Azure OpenAI** resource
2. Deploy `gpt-4o-realtime-preview` model
3. Note the **endpoint** → `AZURE_OPENAI_ENDPOINT` and **key** → `AZURE_OPENAI_API_KEY`
4. Note the deployment name → `AZURE_OPENAI_REALTIME_DEPLOYMENT`

---

## Future: Web Service Extension

To expose the pipeline as a web service (e.g. for browser/mobile clients):

1. Add FastAPI to dependencies
2. Create a WebSocket endpoint that accepts `MediaRecorder` PCM chunks
3. Feed chunks into `PushAudioInputStream` on the Azure Speech SDK
4. Stream TTS audio back as base64-encoded chunks
5. Expose REST endpoints for configuration and health checks

This is intentionally not part of V1 (local desktop).
