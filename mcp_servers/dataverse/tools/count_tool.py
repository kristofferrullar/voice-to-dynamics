"""count_records MCP tool — returns the number of records matching a filter."""
from __future__ import annotations

from mcp_servers.dataverse.client import DataverseClient
from mcp_servers.dataverse.models import CountResult
from mcp_servers.dataverse.tools._validation import validate_table, validate_filter


async def count_records(table_name: str, filter_expression: str = "") -> dict:
    """Count records in a Dataverse table matching an optional OData filter.

    Args:
        table_name: Logical entity name (e.g. "opportunity"). Must be in allowed_tables.yaml.
        filter_expression: Optional OData $filter expression (e.g. "statecode eq 0").
    """
    entity_set = validate_table(table_name, required_permission="query")
    if filter_expression:
        validate_filter(filter_expression)

    primary_key = _primary_key(table_name)
    query_parts = [f"$select={primary_key}", "$count=true", "$top=1"]
    if filter_expression:
        query_parts.append(f"$filter={filter_expression}")

    client = DataverseClient()
    data = await client.get(entity_set, "&".join(query_parts))
    count = data.get("@odata.count", len(data.get("value", [])))
    return CountResult(count=int(count), entity_set=entity_set).model_dump()


def _primary_key(table_name: str) -> str:
    _keys = {
        "opportunity": "opportunityid",
        "account": "accountid",
        "contact": "contactid",
        "lead": "leadid",
        "task": "activityid",
        "phonecall": "activityid",
        "systemuser": "systemuserid",
    }
    return _keys.get(table_name, f"{table_name}id")
