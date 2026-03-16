from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract base for LLM providers used by the agent.

    Implement this to add a new LLM backend (e.g. Azure OpenAI).
    Register in src/providers/factory.py and config/pipeline.yaml.
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Run a completion and return the raw response dict.

        Returns a dict with at minimum:
          - "content": list of content blocks
          - "stop_reason": str  ("end_turn" | "tool_use" | ...)
        """
