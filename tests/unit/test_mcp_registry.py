"""Unit tests for MCPRegistry config loading."""
import pytest

from src.mcp.registry import MCPRegistry


def test_registry_instantiates():
    registry = MCPRegistry()
    assert registry is not None


def test_registry_config_loads():
    # Smoke test: loading the YAML config should not raise
    registry = MCPRegistry()
    config = registry._load_config()
    assert "servers" in config


def test_registry_has_dataverse_server():
    registry = MCPRegistry()
    config = registry._load_config()
    names = [s["name"] for s in config["servers"]]
    assert "dataverse" in names
