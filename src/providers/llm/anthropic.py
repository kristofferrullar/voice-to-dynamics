from typing import Any

import anthropic

from config.settings import get_settings
from src.providers.llm.base import LLMProvider


class AnthropicLLMProvider(LLMProvider):
    """Claude LLM provider via the Anthropic SDK."""

    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        self._model = model
        settings = get_settings()
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def complete(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 1024,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        response = await self._client.messages.create(**kwargs)
        return {
            "content": [block.model_dump() for block in response.content],
            "stop_reason": response.stop_reason,
            "usage": response.usage.model_dump(),
        }
