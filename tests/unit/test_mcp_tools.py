"""Unit tests for MCP tool validation — no live Dataverse required."""
import pytest

from mcp_servers.dataverse.tools._validation import (
    validate_table,
    validate_columns,
    validate_filter,
)


def test_validate_table_allowed():
    entity_set = validate_table("opportunity", "query")
    assert entity_set == "opportunities"


def test_validate_table_unknown():
    with pytest.raises(ValueError, match="not in the allowed list"):
        validate_table("invoice", "query")


def test_validate_table_no_permission():
    with pytest.raises(PermissionError, match="not permitted"):
        validate_table("account", "create")


def test_validate_columns_valid():
    validate_columns("opportunity", ["name", "statecode", "estimatedvalue"])


def test_validate_columns_injection():
    with pytest.raises(ValueError, match="invalid characters"):
        validate_columns("opportunity", ["name; DROP TABLE"])


def test_validate_filter_clean():
    validate_filter("statecode eq 0 and _ownerid_value eq some-guid")


def test_validate_filter_injection():
    with pytest.raises(ValueError, match="disallowed pattern"):
        validate_filter("statecode eq 0; DROP TABLE opportunities")


def test_validate_filter_too_long():
    with pytest.raises(ValueError, match="too long"):
        validate_filter("x" * 2001)
