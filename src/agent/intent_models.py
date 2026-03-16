from dataclasses import dataclass, field


@dataclass
class ActionRecord:
    tool_name: str
    arguments: dict
    result: object
    success: bool
    error: str | None = None


@dataclass
class AgentResponse:
    result_summary: str       # Short Swedish sentence for TTS
    intention: str            # What the agent understood
    extracted_data: dict      # Key values extracted from utterance
    mapped_entity: str        # Which Dataverse entity was targeted (or "unknown")
    actions_performed: list[ActionRecord] = field(default_factory=list)
    success: bool = True
    error: str | None = None
