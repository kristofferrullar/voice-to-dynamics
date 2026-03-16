"""Dataverse MCP server entry point.

Exposes tools for querying, counting, creating, and updating Dataverse records.
Runs via stdio transport (spawned by the MCPRegistry).

Start manually for testing:
  python -m mcp_servers.dataverse.server
"""
from fastmcp import FastMCP

from mcp_servers.dataverse.client import get_client
from mcp_servers.dataverse.tools.count_tool import count_records
from mcp_servers.dataverse.tools.create_tool import create_record
from mcp_servers.dataverse.tools.delete_tool import delete_record
from mcp_servers.dataverse.tools.query_tool import query_records
from mcp_servers.dataverse.tools.update_tool import update_record

mcp = FastMCP(
    name="dataverse",
    instructions=(
        "Tools for Microsoft Dataverse / Dynamics 365. "
        "Always check allowed_tables and required permissions before calling. "
        "Use count_records for numeric queries, query_records for list queries."
    ),
)


@mcp.tool()
async def query_records_tool(
    table_name: str,
    select_columns: list[str],
    filter_expression: str = "",
    order_by: str = "",
    top: int = 20,
    include_count: bool = False,
) -> dict:
    """Query records from a Dataverse table.

    table_name: Logical entity name (e.g. 'opportunity', 'account').
    select_columns: List of column logical names to return.
    filter_expression: OData $filter string (e.g. 'statecode eq 0').
    order_by: OData $orderby string.
    top: Max records to return (capped at 200).
    include_count: Whether to include total count.
    """
    return await query_records(table_name, select_columns, filter_expression, order_by, top, include_count)


@mcp.tool()
async def count_records_tool(table_name: str, filter_expression: str = "") -> dict:
    """Count records in a Dataverse table matching an optional filter.

    table_name: Logical entity name.
    filter_expression: OData $filter string.
    """
    return await count_records(table_name, filter_expression)


@mcp.tool()
async def create_record_tool(table_name: str, data: dict) -> dict:
    """Create a new record in a Dataverse table.

    table_name: Logical entity name (must have 'create' permission).
    data: Column → value map for the new record.
    """
    return await create_record(table_name, data)


@mcp.tool()
async def update_record_tool(table_name: str, record_id: str, data: dict) -> dict:
    """Update an existing record in a Dataverse table.

    table_name: Logical entity name (must have 'update' permission).
    record_id: GUID of the record.
    data: Column → value map of fields to update.
    """
    return await update_record(table_name, record_id, data)


@mcp.tool()
async def delete_record_tool(table_name: str, record_id: str) -> dict:
    """Delete a record. DISABLED by default — set ALLOW_DATAVERSE_DELETE=true to enable.

    table_name: Logical entity name (must have 'delete' permission).
    record_id: GUID of the record to delete.
    """
    return await delete_record(table_name, record_id)


@mcp.tool()
async def get_current_user() -> dict:
    """Return the systemuserid and basic info for the authenticated service principal.

    Use this to resolve 'my' / 'mine' queries before filtering by _ownerid_value.
    """
    return await get_client().get_current_user()


if __name__ == "__main__":
    mcp.run()
