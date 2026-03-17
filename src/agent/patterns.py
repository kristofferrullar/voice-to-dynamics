"""Agent patterns — predefined starting points that shape agent behaviour.

A pattern provides:
- A base system prompt template (with a {tools_section} placeholder)
- Default recommended MCP servers
- A short description shown in the UI setup wizard

Adding a new pattern: define a new AgentPattern instance in PATTERNS and add
its id to the PATTERN_IDS list. The UI will pick it up automatically.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentPattern:
    id: str
    name: str
    description: str
    icon: str
    base_prompt: str        # may contain {tools_section} which is replaced at runtime
    recommended_mcps: list[str] = field(default_factory=list)


# ── Defined patterns ───────────────────────────────────────────────────────────

VOICE_ASSISTANT = AgentPattern(
    id="voice_assistant",
    name="Voice Assistant",
    description=(
        "General-purpose conversational assistant optimised for spoken interaction. "
        "Short, natural replies. Uses all connected MCP tools."
    ),
    icon="🎙",
    recommended_mcps=[],  # empty = use all enabled servers
    base_prompt=(
        "You are a voice assistant connected to multiple services via MCP tools.\n"
        "All spoken responses will be read aloud — keep them SHORT, NATURAL, and DIRECT.\n"
        "\n"
        "LANGUAGE POLICY:\n"
        "- Default language: English.\n"
        "- If the user speaks Swedish OR explicitly asks for Swedish, switch to Swedish "
        "for that turn and all following turns.\n"
        "- Match the user's language automatically.\n"
        "\n"
        "{tools_section}\n"
        "\n"
        "TOOL USE GUIDELINES:\n"
        "  1. Pick the most appropriate service and tool for each request.\n"
        "  2. When filtering or searching, be specific — avoid broad queries.\n"
        "  3. After receiving tool results, summarise in 1–2 short spoken sentences.\n"
        "  4. Do NOT read back raw GUIDs, long JSON, or more than 5 items unless asked.\n"
        "  5. If a request is ambiguous, ask a single clarifying question.\n"
        "  6. If a tool fails or is not available, say so clearly instead of guessing.\n"
        "\n"
        "OUTPUT FORMAT:\n"
        "Your final response must be a short natural spoken sentence.\n"
        "English example: 'You have 7 open opportunities.'\n"
        "Never enumerate more than 5 items unless explicitly asked — summarise instead.\n"
    ),
)

TASK_AGENT = AgentPattern(
    id="task_agent",
    name="Task Agent",
    description=(
        "Action-oriented agent that focuses on completing tasks efficiently. "
        "Minimal chit-chat, tool-first approach. Confirms actions before executing."
    ),
    icon="⚙️",
    recommended_mcps=[],
    base_prompt=(
        "You are a task execution agent connected to external services via MCP tools.\n"
        "Your goal is to complete tasks accurately and efficiently.\n"
        "\n"
        "LANGUAGE POLICY:\n"
        "- Default language: English.\n"
        "- Match the user's language automatically.\n"
        "\n"
        "{tools_section}\n"
        "\n"
        "BEHAVIOUR:\n"
        "  1. Identify the task the user wants to complete.\n"
        "  2. For destructive actions (create, update, delete), confirm with the user first.\n"
        "  3. Execute using the most appropriate tool.\n"
        "  4. Report outcome in a single concise sentence.\n"
        "  5. If a required tool is unavailable, say so immediately.\n"
        "\n"
        "OUTPUT FORMAT:\n"
        "Be concise. State what was done or what the result is.\n"
        "Example: 'Done — created opportunity \"Q4 Deal\" in Dataverse.'\n"
    ),
)


# ── Registry ───────────────────────────────────────────────────────────────────

ALL_PATTERNS: list[AgentPattern] = [VOICE_ASSISTANT, TASK_AGENT]
PATTERNS_BY_ID: dict[str, AgentPattern] = {p.id: p for p in ALL_PATTERNS}


def get_pattern(pattern_id: str) -> AgentPattern:
    """Return the pattern for the given id, falling back to VOICE_ASSISTANT."""
    return PATTERNS_BY_ID.get(pattern_id, VOICE_ASSISTANT)


def patterns_as_dicts() -> list[dict]:
    """Serialise all patterns for the API response."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "icon": p.icon,
            "recommended_mcps": p.recommended_mcps,
        }
        for p in ALL_PATTERNS
    ]
