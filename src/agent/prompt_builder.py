"""PromptBuilder — assembles the agent system prompt from live MCP data and config.

The prompt is built once per agent session after MCP servers have connected,
so it accurately reflects which services and tools are actually available.

Sections:
  1. Role + language policy
  2. Connected MCP servers + their tools  (built from live MCPRegistry data)
  3. Dataverse entity schemas             (injected only when credentials are set)
  4. Tool-use guidelines
  5. Output format
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from config.settings import get_settings
from src.agent.schema_loader import EntitySchema, load_all

_ALLOWED_TABLES_PATH = (
    Path(__file__).resolve().parents[2] / "mcp_servers" / "dataverse" / "allowed_tables.yaml"
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _dataverse_configured() -> bool:
    s = get_settings()
    return bool(s.azure_tenant_id and s.azure_client_id and s.dataverse_environment_url)


def _load_allowed_tables() -> dict[str, Any]:
    if not _ALLOWED_TABLES_PATH.exists():
        return {}
    return yaml.safe_load(_ALLOWED_TABLES_PATH.read_text()).get("allowed_tables", {})


def _render_entity_block(schema: EntitySchema, permissions: list[str]) -> str:
    lines = [
        f"=== ENTITY: {schema.logical_name} ({schema.display_name_sv}) ===",
        f"EntitySet: {schema.entity_set}",
        f"Permissions: {', '.join(permissions)}",
        f"Intent keywords: {', '.join(schema.intent_triggers)}",
        "",
        "Columns (logical_name → label → type → filterable):",
    ]
    for attr in schema.attributes:
        filterable = "filterable" if attr.filterable else "not filterable"
        line = f"  - {attr.logical_name} → {attr.display_name_sv} → {attr.type} ({filterable})"
        if attr.common_values:
            values = ", ".join(f"{k}={v}" for k, v in attr.common_values.items())
            line += f" [{values}]"
        if attr.note:
            line += f"  # {attr.note}"
        lines.append(line)

    if schema.query_templates:
        lines.append("")
        lines.append("Pre-built query templates:")
        for key, tmpl in schema.query_templates.items():
            lines.append(f"  [{key}]")
            lines.append(f"    Use when: {tmpl.description}")
            lines.append(f"    OData: {tmpl.odata}")
            lines.append(f"    $select: {tmpl.select}")

    return "\n".join(lines)


def _build_servers_section(server_summaries: list[dict[str, Any]]) -> str:
    """Generate the 'available services' block from live registry data."""
    if not server_summaries:
        return (
            "No MCP servers are currently connected.\n"
            "You cannot use any external tools in this session.\n"
            "Answer from your own knowledge, or let the user know no tools are available."
        )

    lines = ["You have access to the following services via MCP tools:\n"]
    for srv in server_summaries:
        name        = srv["name"]
        description = srv.get("description", "")
        tools       = srv.get("tools", [])

        header = f"  • {name}"
        if description:
            header += f": {description}"
        lines.append(header)

        if tools:
            preview = ", ".join(tools[:5])
            if len(tools) > 5:
                preview += f" … (+{len(tools) - 5} more)"
            lines.append(f"    Tools: {preview}")

    lines.append(
        "\nChoose whichever tools best match the user's request. "
        "You are not limited to any single service."
    )
    return "\n".join(lines)


# ── Public API ─────────────────────────────────────────────────────────────────

def build(server_summaries: list[dict[str, Any]] | None = None) -> str:
    """Build the system prompt.

    Args:
        server_summaries: Output of ``MCPRegistry.get_server_summaries()``.
                          Pass ``None`` or an empty list when no servers are connected.
    """
    summaries = server_summaries or []

    # ── Section 1: Role + language policy ─────────────────────────────────────
    section1 = (
        "You are a voice assistant connected to multiple services via MCP tools.\n"
        "All spoken responses will be read aloud — keep them SHORT, NATURAL, and DIRECT.\n"
        "\n"
        "LANGUAGE POLICY:\n"
        "- Default language: English.\n"
        "- If the user speaks Swedish OR explicitly asks for Swedish, switch to Swedish "
        "for that turn and all following turns.\n"
        "- Match the user's language automatically.\n"
    )

    # ── Section 2: Connected MCP servers (dynamic from live registry) ──────────
    section2 = _build_servers_section(summaries)

    # ── Section 3: Dataverse schemas (only when credentials are set) ───────────
    if _dataverse_configured():
        schemas = load_all()
        allowed = _load_allowed_tables()

        table_lines = ["DATAVERSE — Allowed tables and permissions:\n"]
        for entity_name, meta in allowed.items():
            perms   = ", ".join(meta.get("permissions", []))
            display = meta.get("display_name", entity_name)
            table_lines.append(f"  - {entity_name} ({display}): {perms}")
        table_lines.append("\nYou MUST NOT access any Dataverse table not in this list.\n")

        schema_blocks = [
            _render_entity_block(
                schema,
                allowed.get(entity_name, {}).get("permissions", ["query"]),
            )
            for entity_name, schema in schemas.items()
        ]
        section3 = "\n".join(table_lines) + "\n\n" + "\n\n".join(schema_blocks)
    else:
        section3 = (
            "DATAVERSE — Not configured.\n"
            "Do NOT attempt to call any Dataverse tools. "
            "If the user asks about Dataverse or Dynamics 365, "
            "tell them it is not configured yet."
        )

    # ── Section 4: Tool-use guidelines ────────────────────────────────────────
    section4 = (
        "TOOL USE GUIDELINES:\n"
        "  1. Pick the most appropriate service and tool for each request.\n"
        "  2. When filtering or searching, be specific — avoid broad queries.\n"
        "  3. After receiving tool results, summarise in 1–2 short spoken sentences.\n"
        "  4. Do NOT read back raw GUIDs, long JSON, or more than 5 items unless asked.\n"
        "  5. If a request is ambiguous, ask a single clarifying question.\n"
        "  6. If a tool fails or is not available, say so clearly instead of guessing.\n"
    )

    if _dataverse_configured():
        section4 += (
            "\nDataverse-specific:\n"
            "  7. Match the user's intent to an entity using its intent_triggers.\n"
            "  8. Prefer pre-built query_templates over custom queries.\n"
            "  9. For custom filters, use ONLY columns marked 'filterable'.\n"
            " 10. Always use $select to limit columns to what is needed.\n"
            " 11. For 'my'/'mine' queries, call get_current_user first.\n"
        )

    # ── Section 5: Output format ───────────────────────────────────────────────
    section5 = (
        "OUTPUT FORMAT:\n"
        "Your final response must be a short natural spoken sentence.\n"
        "English example: 'You have 7 open opportunities.'\n"
        "Swedish example: 'Du har 7 öppna affärsmöjligheter.'\n"
        "Never enumerate more than 5 items unless explicitly asked — summarise instead.\n"
    )

    return "\n\n---\n\n".join([section1, section2, section3, section4, section5])


def invalidate_cache() -> None:
    """No-op kept for backward compatibility.

    Prompt caching is now per-MCPAgent instance and is automatically invalidated
    when the agent is recreated after a config change.
    """
