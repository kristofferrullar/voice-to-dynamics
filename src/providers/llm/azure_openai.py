"""Azure OpenAI LLM provider stub.

Implement using openai.AsyncAzureOpenAI.
Set ``agent.provider: azure_openai`` in config/pipeline.yaml to activate.
"""
from typing import Any

from src.providers.llm.base import LLMProvider


class AzureOpenAILLMProvider(LLMProvider):
    """Azure OpenAI LLM provider (stub — not yet implemented)."""

    async def complete(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("AzureOpenAILLMProvider is not yet implemented")
