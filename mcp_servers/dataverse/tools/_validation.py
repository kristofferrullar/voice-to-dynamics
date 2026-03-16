"""Shared validation logic for all Dataverse MCP tools.

Every tool calls these functions before touching the Dataverse API.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_ALLOWED_TABLES_PATH = Path(__file__).resolve().parents[1] / "allowed_tables.yaml"

# Blocks obvious injection patterns in $filter strings
_FILTER_BLOCKLIST = re.compile(r"[;]|--|\bdrop\b|\bdelete\b|\bexec\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def _load_allowed_tables() -> dict[str, Any]:
    return yaml.safe_load(_ALLOWED_TABLES_PATH.read_text()).get("allowed_tables", {})


def validate_table(table_name: str, required_permission: str) -> str:
    """Validate table_name is allowed and has the required permission.

    Returns the entity_set name (used in OData URLs).
    Raises ValueError or PermissionError on failure.
    """
    allowed = _load_allowed_tables()
    if table_name not in allowed:
        raise ValueError(
            f"Table '{table_name}' is not in the allowed list. "
            f"Allowed: {list(allowed.keys())}"
        )
    meta = allowed[table_name]
    if required_permission not in meta.get("permissions", []):
        raise PermissionError(
            f"Operation '{required_permission}' is not permitted on table '{table_name}'. "
            f"Allowed operations: {meta.get('permissions', [])}"
        )
    return meta["entity_set"]


def validate_columns(table_name: str, columns: list[str]) -> None:
    """Validate that all column names are safe identifiers (letters, digits, underscore).

    Full column-level schema validation happens in the schema loader;
    here we guard against injection via column name strings.
    """
    pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    for col in columns:
        if not pattern.match(col):
            raise ValueError(f"Column name '{col}' contains invalid characters")


def validate_filter(filter_expression: str) -> None:
    """Block obvious injection patterns in OData $filter strings."""
    if _FILTER_BLOCKLIST.search(filter_expression):
        raise ValueError(f"Filter expression contains disallowed pattern: '{filter_expression}'")
    if len(filter_expression) > 2000:
        raise ValueError("Filter expression is too long (max 2000 characters)")
