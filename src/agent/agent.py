"""Core agent loop.

Receives a cleaned utterance, runs the Claude tool-use loop via the LLM provider,
routes tool calls through the MCP registry, and returns an AgentResponse.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from src.agent.intent_models import ActionRecord, AgentResponse
from src.agent.prompt_builder import build as build_system_prompt
from src.mcp.registry import MCPRegistry
from src.providers.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class DataverseAgent:
    def __init__(self, llm: LLMProvider, mcp: MCPRegistry, max_iterations: int = 10) -> None:
        self._llm = llm
        self._mcp = mcp
        self._max_iterations = max_iterations
        self._system_prompt: str | None = None

    async def _get_system_prompt(self) -> str:
        if not self._system_prompt:
            self._system_prompt = build_system_prompt()
        return self._system_prompt

    async def process(self, utterance: str) -> AgentResponse:
        system = await self._get_system_prompt()
        tools = _convert_tools(await self._mcp.get_tools())
        messages: list[dict[str, Any]] = [{"role": "user", "content": utterance}]
        actions: list[ActionRecord] = []

        for _ in range(self._max_iterations):
            response = await self._llm.complete(messages, system=system, tools=tools)
            stop_reason = response.get("stop_reason", "end_turn")
            content = response.get("content", [])

            # Append assistant message
            messages.append({"role": "assistant", "content": content})

            if stop_reason != "tool_use":
                # Final text response
                text = _extract_text(content)
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
                if block.get("type") != "tool_use":
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

        return AgentResponse(
            result_summary="Förlåt, jag kunde inte slutföra din förfrågan.",
            intention=utterance,
            extracted_data={},
            mapped_entity="unknown",
            actions_performed=actions,
            success=False,
            error="Max iterations reached",
        )


def _extract_text(content: list[dict[str, Any]]) -> str:
    for block in content:
        if block.get("type") == "text":
            return block.get("text", "")
    return "Klart."


def _convert_tools(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert MCP tool format to Anthropic tool format."""
    converted = []
    for tool in mcp_tools:
        converted.append(
            {
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "input_schema": tool.get("inputSchema", {"type": "object", "properties": {}}),
            }
        )
    return converted
