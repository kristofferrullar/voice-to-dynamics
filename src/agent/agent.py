"""Core agent loop.

Receives a cleaned utterance, runs the Claude tool-use loop via the LLM provider,
routes tool calls through the MCP registry, and returns an AgentResponse.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from src.agent.intent_models import ActionRecord, AgentResponse
from src.agent.memory import ConversationMemory
from src.agent.prompt_builder import build as build_system_prompt
from src.mcp.registry import MCPRegistry
from src.providers.llm.base import LLMProvider

logger = logging.getLogger(__name__)

_STOP_REASON_TOOL_USE = "tool_use"


class MCPAgent:
    """General-purpose agent that routes requests through any connected MCP server."""

    def __init__(
        self,
        llm: LLMProvider,
        mcp: MCPRegistry,
        max_iterations: int = 10,
        memory: ConversationMemory | None = None,
    ) -> None:
        self._llm = llm
        self._mcp = mcp
        self._max_iterations = max_iterations
        self._memory = memory or ConversationMemory(enabled=False)
        # Built lazily on the first process() call using the live server list,
        # so the prompt accurately reflects whichever MCPs actually connected.
        self._system_prompt: str | None = None

    def reset_memory(self) -> None:
        """Clear all conversation history."""
        self._memory.reset()

    async def process(self, utterance: str) -> AgentResponse:
        # Build the prompt once per agent lifetime from the live server summaries.
        if self._system_prompt is None:
            self._system_prompt = build_system_prompt(self._mcp.get_server_summaries())
        system = self._system_prompt
        tools = _convert_tools(await self._mcp.get_tools())

        history = self._memory.get_history()
        messages: list[dict[str, Any]] = history + [{"role": "user", "content": utterance}]
        turn_start = len(history)
        actions: list[ActionRecord] = []

        for _ in range(self._max_iterations):
            response = await self._llm.complete(messages, system=system, tools=tools)
            stop_reason = response.get("stop_reason", "end_turn")
            content = response.get("content", [])

            messages.append({"role": "assistant", "content": content})

            if stop_reason != _STOP_REASON_TOOL_USE:
                text = _extract_text(content)
                self._memory.add_turn(messages[turn_start:])
                return AgentResponse(
                    result_summary=text,
                    intention=utterance,
                    extracted_data={},
                    mapped_entity="unknown",
                    actions_performed=actions,
                    success=True,
                )

            # Process tool calls
            tool_results: list[dict[str, Any]] = []
            for block in content:
                if block.get("type") != _STOP_REASON_TOOL_USE:
                    continue
                tool_name = block["name"]
                tool_args = block.get("input", {})
                tool_use_id = block["id"]
                logger.debug("Tool call: %s(%s)", tool_name, tool_args)

                try:
                    result = await self._mcp.call_tool(tool_name, tool_args)
                    result_text = json.dumps(result) if not isinstance(result, str) else result
                    actions.append(ActionRecord(tool_name=tool_name, arguments=tool_args, result=result, success=True))
                except Exception as exc:
                    result_text = f"Error: {exc}"
                    actions.append(ActionRecord(tool_name=tool_name, arguments=tool_args, result=None, success=False, error=str(exc)))
                    logger.warning("Tool '%s' failed: %s", tool_name, exc)

                tool_results.append(
                    {"type": "tool_result", "tool_use_id": tool_use_id, "content": result_text}
                )

            messages.append({"role": "user", "content": tool_results})

        self._memory.add_turn(messages[turn_start:])
        return AgentResponse(
            result_summary="Sorry, I wasn't able to complete your request.",
            intention=utterance,
            extracted_data={},
            mapped_entity="unknown",
            actions_performed=actions,
            success=False,
            error="Max iterations reached",
        )


# Backward-compatible alias — existing imports continue to work.
DataverseAgent = MCPAgent


def _extract_text(content: list[dict[str, Any]]) -> str:
    for block in content:
        if block.get("type") == "text":
            return block.get("text", "")
    return "Done."


def _convert_tools(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert MCP tool format to Anthropic tool format."""
    return [
        {
            "name": tool.get("name"),
            "description": tool.get("description", ""),
            "input_schema": tool.get("inputSchema", {"type": "object", "properties": {}}),
        }
        for tool in mcp_tools
    ]
