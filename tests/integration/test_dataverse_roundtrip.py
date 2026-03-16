"""Integration tests — require a real .env with Dataverse credentials.

Run with:
  pytest tests/integration/ -v
"""
import os
import pytest

# Skip if credentials not configured
pytestmark = pytest.mark.skipif(
    not os.getenv("AZURE_TENANT_ID"),
    reason="Dataverse credentials not configured in .env",
)


@pytest.mark.asyncio
async def test_get_current_user():
    from mcp_servers.dataverse.client import DataverseClient
    client = DataverseClient()
    user = await client.get_current_user()
    assert "UserId" in user


@pytest.mark.asyncio
async def test_count_opportunities():
    from mcp_servers.dataverse.tools.count_tool import count_records
    result = await count_records("opportunity", "statecode eq 0")
    assert "count" in result
    assert isinstance(result["count"], int)


@pytest.mark.asyncio
async def test_query_opportunities():
    from mcp_servers.dataverse.tools.query_tool import query_records
    result = await query_records(
        table_name="opportunity",
        select_columns=["name", "statecode"],
        filter_expression="statecode eq 0",
        top=5,
    )
    assert "records" in result
    assert isinstance(result["records"], list)
