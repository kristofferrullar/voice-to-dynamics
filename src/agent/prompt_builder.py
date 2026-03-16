"""PromptBuilder — assembles the agent system prompt from schema files and config.

The prompt is built once at startup and cached. It has five sections:
  1. Role + language policy
  2. Allowed Dataverse tables + permissions
  3. Entity schemas (compact YAML injection)
  4. Tool use instructions (all MCP servers)
  5. Output format
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from config.settings import get_settings
from src.agent.schema_loader import EntitySchema, load_all

_ALLOWED_TABLES_PATH = Path(__file__).resolve().parents[2] / "mcp_servers" / "dataverse" / "allowed_tables.yaml"
_MCP_SERVERS_PATH = Path(__file__).resolve().parents[2] / "config" / "mcp_servers.yaml"


def _dataverse_configured() -> bool:
    s = get_settings()
    return bool(s.azure_tenant_id and s.azure_client_id and s.dataverse_environment_url)


def _load_allowed_tables() -> dict[str, Any]:
    if not _ALLOWED_TABLES_PATH.exists():
        return {}
    return yaml.safe_load(_ALLOWED_TABLES_PATH.read_text()).get("allowed_tables", {})


def _load_mcp_servers() -> list[dict[str, Any]]:
    if not _MCP_SERVERS_PATH.exists():
        return []
    return yaml.safe_load(_MCP_SERVERS_PATH.read_text()).get("servers", [])


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


def invalidate_cache() -> None:
    """Call this if credentials change at runtime so the prompt is rebuilt."""
    build.cache_clear()


@lru_cache(maxsize=1)
def build() -> str:
    schemas = load_all()
    allowed = _load_allowed_tables()
    mcp_servers = _load_mcp_servers()

    # Section 1: Role + language policy
    section1 = (
        "You are a voice assistant connected to multiple services via MCP tools.\n"
        "All spoken responses will be read aloud — keep them SHORT, NATURAL, and DIRECT.\n"
        "\n"
        "LANGUAGE POLICY:\n"
        "- Default language: English.\n"
        "- If the user speaks Swedish OR explicitly asks for Swedish, switch to Swedish for that turn and all following turns.\n"
        "- Match the user's language automatically.\n"
    )

    # Section 2: Available MCP servers
    server_lines = ["You have access to the following MCP servers and their tools:\n"]
    for srv in mcp_servers:
        if srv.get("enabled", True):
            server_lines.append(f"  • {srv['name']}: {srv.get('description', '(no description)')}")
    server_lines.append(
        "\nUse whichever tools are appropriate for the user's request. "
        "You are NOT limited to Dataverse — use GitHub, or any other available server when relevant."
    )
    section2 = "\n".join(server_lines)

    # Section 3: Dataverse tables + entity schemas (only when credentials are configured)
    if _dataverse_configured():
        table_lines = ["DATAVERSE — Allowed tables and permissions:\n"]
        for entity_name, meta in allowed.items():
            perms = ", ".join(meta.get("permissions", []))
            display = meta.get("display_name", entity_name)
            table_lines.append(f"  - {entity_name} ({display}): {perms}")
        table_lines.append("\nYou MUST NOT access any Dataverse table not in this list.\n")
        section3_header = "\n".join(table_lines)

        schema_blocks: list[str] = []
        for entity_name, schema in schemas.items():
            meta = allowed.get(entity_name, {})
            permissions = meta.get("permissions", ["query"])
            schema_blocks.append(_render_entity_block(schema, permissions))
        section3 = section3_header + "\n\n" + "\n\n".join(schema_blocks)
    else:
        section3 = (
            "DATAVERSE — Not configured.\n"
            "Do NOT attempt to call any Dataverse tools. "
            "If the user asks about Dataverse or Dynamics 365, tell them it is not configured yet."
        )

    # Section 4: Tool use instructions
    section4 = (
        "TOOL USE GUIDELINES:\n"
        "GitHub:\n"
        "  1. Use GitHub tools for repo, issue, PR, code search, and file operations.\n"
        "  2. When searching code or issues, be specific with search terms.\n"
        "\n"
        "Dataverse (only if configured):\n"
        "  3. Match the user's intent to an entity using intent_triggers.\n"
        "  4. Prefer pre-built query_templates over custom queries.\n"
        "  5. For custom filters, use ONLY columns marked 'filterable'.\n"
        "  6. Always use $select to limit columns to what is needed.\n"
        "  7. For 'my' / 'mine' queries, call get_current_user first to resolve the user id.\n"
        "\n"
        "General:\n"
        "  8. After receiving tool results, summarise in 1-2 short spoken sentences.\n"
        "  9. Do NOT read back raw GUIDs, long JSON, or more than 5 items unless asked.\n"
        " 10. If a request is ambiguous, ask a single clarifying question.\n"
        " 11. If a tool is not available or not configured, say so clearly instead of trying anyway.\n"
    )

    # Section 5: Output format
    section5 = (
        "OUTPUT FORMAT:\n"
        "Your final response must be a short natural spoken sentence.\n"
        "English example: 'You have 7 open opportunities.'\n"
        "Swedish example: 'Du har 7 öppna affärsmöjligheter.'\n"
        "Never enumerate more than 5 items unless explicitly asked — summarise instead.\n"
    )

    return "\n\n---\n\n".join([section1, section2, section3, section4, section5])
