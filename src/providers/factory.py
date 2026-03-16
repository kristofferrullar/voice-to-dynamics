"""ProviderFactory — reads config/pipeline.yaml and instantiates concrete providers.

Adding a new provider:
1. Implement the ABC in the relevant providers/<category>/ package.
2. Add the new provider key to the match block below.
3. Set the key in config/pipeline.yaml.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from src.providers.stt.base import STTProvider
    from src.providers.tts.base import TTSProvider
    from src.providers.conversation.base import ConversationHost
    from src.providers.llm.base import LLMProvider

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "pipeline.yaml"


def _load_pipeline_config() -> dict[str, Any]:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


class ProviderFactory:
    """Reads pipeline.yaml and returns configured provider instances."""

    def __init__(self) -> None:
        self._cfg = _load_pipeline_config()

    def get_stt(self) -> "STTProvider":
        stt_cfg = self._cfg.get("stt", {})
        provider = stt_cfg.get("provider", "azure")
        language = stt_cfg.get("language", "sv-SE")
        filler_removal = stt_cfg.get("filler_word_removal", True)

        match provider:
            case "azure":
                from src.providers.stt.azure import AzureSTTProvider
                return AzureSTTProvider(language=language, filler_word_removal=filler_removal)
            case "whisper":
                from src.providers.stt.whisper import WhisperSTTProvider
                return WhisperSTTProvider()
            case _:
                raise ValueError(f"Unknown STT provider: '{provider}'")

    def get_tts(self) -> "TTSProvider":
        tts_cfg = self._cfg.get("tts", {})
        provider = tts_cfg.get("provider", "azure")
        voice = tts_cfg.get("voice", "sv-SE-MattiasNeural")

        match provider:
            case "azure":
                from src.providers.tts.azure import AzureTTSProvider
                return AzureTTSProvider(voice=voice)
            case "openai":
                from src.providers.tts.openai import OpenAITTSProvider
                return OpenAITTSProvider()
            case _:
                raise ValueError(f"Unknown TTS provider: '{provider}'")

    def get_conversation_host(self, tts_speak_fn=None) -> "ConversationHost":  # type: ignore[type-arg]
        host_cfg = self._cfg.get("conversation_host", {})
        provider = host_cfg.get("provider", "azure_realtime")
        system_prompt = host_cfg.get(
            "system_prompt",
            "You are a voice assistant. Reply with exactly one short sentence that acknowledges "
            "what the user asked. Do not perform the action yourself. "
            "If the user speaks Swedish, reply in Swedish instead.",
        )

        match provider:
            case "azure_realtime":
                from src.providers.conversation.azure_realtime import AzureRealtimeConversationHost
                return AzureRealtimeConversationHost(system_prompt=system_prompt)
            case "claude":
                from src.providers.conversation.claude import ClaudeConversationHost
                return ClaudeConversationHost(tts_speak_fn=tts_speak_fn, system_prompt=system_prompt)
            case _:
                raise ValueError(f"Unknown conversation_host provider: '{provider}'")

    def get_llm(self) -> "LLMProvider":
        agent_cfg = self._cfg.get("agent", {})
        provider = agent_cfg.get("provider", "anthropic")
        model = agent_cfg.get("model", "claude-sonnet-4-6")

        match provider:
            case "anthropic":
                from src.providers.llm.anthropic import AnthropicLLMProvider
                return AnthropicLLMProvider(model=model)
            case "azure_openai":
                from src.providers.llm.azure_openai import AzureOpenAILLMProvider
                return AzureOpenAILLMProvider()
            case _:
                raise ValueError(f"Unknown agent LLM provider: '{provider}'")

    def get_memory(self) -> "ConversationMemory":
        from src.agent.memory import ConversationMemory
        memory_cfg = self._cfg.get("agent", {}).get("memory", {})
        return ConversationMemory(
            enabled=memory_cfg.get("enabled", True),
            max_turns=memory_cfg.get("max_turns", 10),
        )

    @property
    def agent_config(self) -> dict[str, Any]:
        return self._cfg.get("agent", {})
