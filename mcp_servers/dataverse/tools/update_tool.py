"""update_record MCP tool — updates an existing Dataverse record."""
from __future__ import annotations

from typing import Any

from mcp_servers.dataverse.client import DataverseClient
from mcp_servers.dataverse.models import UpdateResult
from mcp_servers.dataverse.tools._validation import validate_table, validate_columns


async def update_record(table_name: str, record_id: str, data: dict[str, Any]) -> dict:
    """Update an existing record in a Dataverse table.

    Args:
        table_name: Logical entity name. Must be in allowed_tables.yaml with 'update' permission.
        record_id: GUID of the record to update.
        data: Column → value map of fields to update.
    """
    entity_set = validate_table(table_name, required_permission="update")
    validate_columns(table_name, list(data.keys()))

    client = DataverseClient()
    await client.patch(entity_set, record_id, data)
    return UpdateResult(
        record_id=record_id,
        entity_set=entity_set,
        updated_columns=list(data.keys()),
        success=True,
    ).model_dump()
