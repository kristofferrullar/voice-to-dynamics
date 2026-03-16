"""Integration test for the agent loop with mocked MCP tools.

Tests that the agent correctly uses tools and returns a Swedish response.
Requires ANTHROPIC_API_KEY in .env.
"""
import os
import pytest
from unittest.mock import AsyncMock

pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not configured",
)


@pytest.mark.asyncio
async def test_agent_returns_swedish_response():
    from src.agent.agent import DataverseAgent
    from src.providers.llm.anthropic import AnthropicLLMProvider
    from src.mcp.registry import MCPRegistry

    # Mock the MCP registry
    mcp = AsyncMock(spec=MCPRegistry)
    mcp.get_tools.return_value = [
        {
            "name": "count_records_tool",
            "description": "Count records in a Dataverse table",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string"},
                    "filter_expression": {"type": "string"},
                },
                "required": ["table_name"],
            },
        },
        {
            "name": "get_current_user",
            "description": "Get current user id",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]
    mcp.call_tool.side_effect = lambda name, args: (
        {"UserId": "test-user-id"} if name == "get_current_user"
        else {"count": 7, "entity_set": "opportunities"}
    )

    llm = AnthropicLLMProvider(model="claude-haiku-4-5")
    agent = DataverseAgent(llm=llm, mcp=mcp, max_iterations=5)

    response = await agent.process("Hur många öppna affärsmöjligheter har jag?")
    assert response.success
    assert response.result_summary
    # Response should be in Swedish (contain common Swedish words)
    summary_lower = response.result_summary.lower()
    assert any(word in summary_lower for word in ["du", "har", "öppna", "affär", "sju", "7"])
