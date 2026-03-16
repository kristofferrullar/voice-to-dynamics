"""Conversation memory — retains message history across agent turns.

A "turn" is the complete exchange for one user utterance: the initial user
message, any tool-call/tool-result pairs, and the final assistant reply.
Turns are stored as message slices so the LLM sees full context on every call.

Configuration (pipeline.yaml):
    agent:
      memory:
        enabled: true
        max_turns: 10
        reset_phrases: ["new session", "starta om", "börja om", "reset"]
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Stores per-session conversation history, trimmed to *max_turns* turns."""

    def __init__(self, max_turns: int = 10, enabled: bool = True) -> None:
        self._max_turns = max_turns
        self._enabled = enabled
        self._turns: list[list[dict[str, Any]]] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def get_history(self) -> list[dict[str, Any]]:
        """Return a flat message list covering all stored turns."""
        if not self._enabled:
            return []
        history: list[dict[str, Any]] = []
        for turn in self._turns:
            history.extend(turn)
        return history

    def add_turn(self, messages: list[dict[str, Any]]) -> None:
        """Append one turn's messages and trim to *max_turns* if needed."""
        if not self._enabled or not messages:
            return
        self._turns.append(messages)
        if len(self._turns) > self._max_turns:
            self._turns = self._turns[-self._max_turns :]
        logger.debug(
            "Memory: %d turn(s) stored (%d messages this turn)",
            len(self._turns),
            len(messages),
        )

    def reset(self) -> None:
        """Clear all stored history."""
        self._turns.clear()
        logger.info("Memory: cleared")

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def max_turns(self) -> int:
        return self._max_turns

    @property
    def turn_count(self) -> int:
        return len(self._turns)
