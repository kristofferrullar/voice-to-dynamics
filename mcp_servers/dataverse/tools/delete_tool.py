"""delete_record MCP tool — disabled by default.

Set ALLOW_DATAVERSE_DELETE=true in .env to enable.
This tool is intentionally restricted to prevent accidental data loss.
"""
from __future__ import annotations

import os

from mcp_servers.dataverse.client import DataverseClient
from mcp_servers.dataverse.models import DeleteResult
from mcp_servers.dataverse.tools._validation import validate_table


async def delete_record(table_name: str, record_id: str) -> dict:
    """Delete a record from a Dataverse table.

    This tool is DISABLED by default. Set ALLOW_DATAVERSE_DELETE=true to enable.

    Args:
        table_name: Logical entity name. Must have 'delete' permission in allowed_tables.yaml.
        record_id: GUID of the record to delete.
    """
    if os.getenv("ALLOW_DATAVERSE_DELETE", "false").lower() != "true":
        raise PermissionError(
            "delete_record is disabled. Set ALLOW_DATAVERSE_DELETE=true in .env to enable."
        )
    entity_set = validate_table(table_name, required_permission="delete")
    client = DataverseClient()
    await client.delete(entity_set, record_id)
    return DeleteResult(record_id=record_id, entity_set=entity_set, success=True).model_dump()
