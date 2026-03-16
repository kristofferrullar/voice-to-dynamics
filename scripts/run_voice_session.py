#!/usr/bin/env python
"""Start a full voice session.

Reads configuration from config/pipeline.yaml and config/mcp_servers.yaml.
Requires a populated .env file.

Usage:
  python scripts/run_voice_session.py
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.orchestrator.pipeline import run

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    asyncio.run(run())
