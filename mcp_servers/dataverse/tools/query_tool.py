"""query_records MCP tool — fetches records from a Dataverse table."""
from __future__ import annotations

from mcp_servers.dataverse.client import DataverseClient
from mcp_servers.dataverse.models import QueryResult
from mcp_servers.dataverse.tools._validation import validate_table, validate_columns, validate_filter

_MAX_TOP = 200


async def query_records(
    table_name: str,
    select_columns: list[str],
    filter_expression: str = "",
    order_by: str = "",
    top: int = 20,
    include_count: bool = False,
) -> dict:
    """Query records from a Dataverse table.

    Args:
        table_name: Logical entity name. Must be in allowed_tables.yaml.
        select_columns: Columns to return ($select). Must be allowed for this entity.
        filter_expression: OData $filter expression.
        order_by: OData $orderby expression.
        top: Maximum number of records to return (capped at 200).
        include_count: Whether to include @odata.count in results.
    """
    entity_set = validate_table(table_name, required_permission="query")
    validate_columns(table_name, select_columns)
    if filter_expression:
        validate_filter(filter_expression)

    top = min(top, _MAX_TOP)
    query_parts = [f"$select={','.join(select_columns)}", f"$top={top}"]
    if filter_expression:
        query_parts.append(f"$filter={filter_expression}")
    if order_by:
        query_parts.append(f"$orderby={order_by}")
    if include_count:
        query_parts.append("$count=true")

    client = DataverseClient()
    data = await client.get(entity_set, "&".join(query_parts))
    total_count = int(data["@odata.count"]) if include_count and "@odata.count" in data else None

    return QueryResult(
        records=data.get("value", []),
        total_count=total_count,
        entity_set=entity_set,
        odata_context=data.get("@odata.context", ""),
    ).model_dump()
