#!/usr/bin/env python
"""Start a named MCP server from the registry for testing / development.

Usage:
  python scripts/run_mcp_server.py dataverse
"""
import sys
import subprocess
from pathlib import Path
import yaml

_CONFIG = Path(__file__).resolve().parents[1] / "config" / "mcp_servers.yaml"


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_mcp_server.py <server-name>")
        sys.exit(1)

    name = sys.argv[1]
    config = yaml.safe_load(_CONFIG.read_text())
    server = next((s for s in config.get("servers", []) if s["name"] == name), None)

    if not server:
        available = [s["name"] for s in config.get("servers", [])]
        print(f"Server '{name}' not found. Available: {available}")
        sys.exit(1)

    if server["transport"] != "stdio":
        print(f"Server '{name}' uses {server['transport']} transport — run manually via: {server.get('url', '')}")
        sys.exit(1)

    print(f"Starting MCP server '{name}': {' '.join(server['command'])}")
    subprocess.run(server["command"], cwd=str(Path(__file__).resolve().parents[1]))


if __name__ == "__main__":
    main()
