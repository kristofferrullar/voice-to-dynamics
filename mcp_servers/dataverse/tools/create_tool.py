"""create_record MCP tool — creates a new record in a Dataverse table."""
from __future__ import annotations

from typing import Any

from mcp_servers.dataverse.client import get_client
from mcp_servers.dataverse.models import CreateResult
from mcp_servers.dataverse.tools._validation import validate_table, validate_columns


async def create_record(table_name: str, data: dict[str, Any]) -> dict:
    """Create a new record in a Dataverse table.

    Args:
        table_name: Logical entity name. Must be in allowed_tables.yaml with 'create' permission.
        data: Column → value map for the new record.
    """
    entity_set = validate_table(table_name, required_permission="create")
    validate_columns(table_name, list(data.keys()))

    record_id = await get_client().post(entity_set, data)
    return CreateResult(record_id=record_id, entity_set=entity_set).model_dump()
