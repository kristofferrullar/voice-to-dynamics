# Adding a New MCP Server

The MCP registry (`src/mcp/registry.py`) auto-discovers and connects to all servers listed in `config/mcp_servers.yaml`. Adding a new integration is a two-step process.

## Step 1: Build or obtain an MCP server

Any MCP-compliant server works, regardless of language or framework. Two transport options:

### stdio (subprocess)
The registry spawns the server as a child process and communicates over stdin/stdout. Best for local services.

```yaml
- name: my_service
  enabled: true
  transport: stdio
  command: ["python", "-m", "my_mcp_server.server"]
  description: "My custom service"
```

### SSE (HTTP)
The registry connects to a running HTTP server that implements the MCP SSE transport. Best for remote services.

```yaml
- name: sharepoint
  enabled: true
  transport: sse
  url: http://localhost:8001/sse
  description: "SharePoint document operations"
```

## Step 2: Register in `config/mcp_servers.yaml`

Add an entry with `enabled: true`. On the next `run_voice_session.py` start, the registry will automatically connect and merge the new server's tools into the agent's tool list.

## How the Agent Uses the Tools

The agent receives a **flat merged tool list** from all connected servers. It does not know which server provides which tool — it simply calls the tool by name and the registry routes the call to the correct server.

This means tool names must be unique across all registered servers. If two servers expose a tool with the same name, the last-registered server wins (with a warning in the logs).

## Bundled Dataverse Server

The built-in Dataverse MCP server lives in `mcp_servers/dataverse/`. Use it as a reference implementation for building additional servers.

Key patterns to follow:
- Validate inputs against an allowlist before calling any external API
- Return structured Pydantic models serialised as dicts
- Raise `ValueError` for bad input, `PermissionError` for permission issues, `RuntimeError` for API errors
- Keep tools focused: one tool per operation type
