"""Voice pipeline orchestrator.

Wires together all providers:
  STT → parallel(ConversationHost + Agent) → TTS

The conversation host speaks a brief acknowledgement immediately (~300 ms).
The agent processes the full request and speaks the result (~3-4 s).
"""
from __future__ import annotations

import asyncio
import logging
import signal

from src.agent.agent import MCPAgent
from src.mcp.registry import MCPRegistry
from src.providers.conversation.base import ConversationHost
from src.providers.factory import ProviderFactory
from src.providers.stt.base import STTProvider
from src.providers.tts.base import TTSProvider

logger = logging.getLogger(__name__)


class VoicePipeline:
    def __init__(
        self,
        stt: STTProvider,
        tts: TTSProvider,
        conversation_host: ConversationHost,
        agent: MCPAgent,
        reset_phrases: list[str] | None = None,
    ) -> None:
        self._stt = stt
        self._tts = tts
        self._host = conversation_host
        self._agent = agent
        self._reset_phrases = [p.lower() for p in (reset_phrases or [])]
        self._running = False

    async def run_forever(self) -> None:
        """Start the pipeline and process utterances until stopped."""
        self._running = True
        await self._host.connect()
        await self._stt.start_session()
        logger.info("Voice pipeline started — listening...")

        try:
            async for utterance in self._stt.utterance_stream():
                if not self._running:
                    break
                logger.info("Utterance: %s", utterance.cleaned_text)
                await self._handle(utterance.cleaned_text)
        finally:
            await self._stt.stop_session()
            await self._host.disconnect()
            logger.info("Voice pipeline stopped")

    async def stop(self) -> None:
        self._running = False

    def _is_reset_command(self, text: str) -> bool:
        if not self._reset_phrases:
            return False
        normalized = text.lower().strip()
        return any(phrase in normalized for phrase in self._reset_phrases)

    async def _handle(self, text: str) -> None:
        if self._is_reset_command(text):
            self._agent.reset_memory()
            await self._tts.speak("Memory cleared. Starting a new session.")
            return

        # Run conversation host and agent concurrently
        host_task = asyncio.create_task(self._host.respond_audio(text))
        agent_task = asyncio.create_task(self._agent.process(text))

        # Speak acknowledgement as soon as it is ready
        try:
            await host_task
        except Exception as exc:
            logger.warning("Conversation host error: %s", exc)

        # Wait for agent result and speak it
        try:
            response = await agent_task
            if response.result_summary:
                await self._tts.speak(response.result_summary)
            if not response.success:
                logger.warning("Agent error: %s", response.error)
        except Exception as exc:
            logger.error("Agent error: %s", exc)
            await self._tts.speak("Sorry, something went wrong. Please try again.")


def build_pipeline() -> tuple[VoicePipeline, MCPRegistry]:
    """Build a VoicePipeline from config/pipeline.yaml and config/mcp_servers.yaml."""
    factory = ProviderFactory()
    tts = factory.get_tts()
    stt = factory.get_stt()
    host = factory.get_conversation_host(tts_speak_fn=tts.speak)
    llm = factory.get_llm()
    memory = factory.get_memory()
    max_iter = factory.agent_config.get("max_tool_iterations", 10)
    reset_phrases = factory.agent_config.get("memory", {}).get(
        "reset_phrases", ["new session", "starta om", "börja om", "reset"]
    )

    mcp   = MCPRegistry()
    agent = MCPAgent(llm=llm, mcp=mcp, max_iterations=max_iter, memory=memory)
    return VoicePipeline(stt=stt, tts=tts, conversation_host=host, agent=agent, reset_phrases=reset_phrases), mcp


async def run() -> None:
    """Entry point: build pipeline, connect MCP servers, run."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    pipeline, mcp = build_pipeline()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT,  lambda: asyncio.create_task(pipeline.stop()))
    loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(pipeline.stop()))

    await mcp.connect_all()
    try:
        await pipeline.run_forever()
    finally:
        await mcp.disconnect_all()
