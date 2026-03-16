"""Unit tests for ConversationMemory."""
import pytest

from src.agent.memory import ConversationMemory

_TURN_A = [
    {"role": "user", "content": "Show my opportunities"},
    {"role": "assistant", "content": [{"type": "text", "text": "You have 3 open opportunities."}]},
]
_TURN_B = [
    {"role": "user", "content": "Update the first one"},
    {"role": "assistant", "content": [{"type": "text", "text": "Updated."}]},
]


@pytest.fixture
def memory() -> ConversationMemory:
    return ConversationMemory(max_turns=10)


def test_starts_empty(memory: ConversationMemory) -> None:
    assert memory.get_history() == []
    assert memory.turn_count == 0


def test_add_and_retrieve_turn(memory: ConversationMemory) -> None:
    memory.add_turn(_TURN_A)
    assert memory.turn_count == 1
    assert memory.get_history() == _TURN_A


def test_history_is_flat_across_turns(memory: ConversationMemory) -> None:
    memory.add_turn(_TURN_A)
    memory.add_turn(_TURN_B)
    assert memory.get_history() == _TURN_A + _TURN_B


def test_reset_clears_all_turns(memory: ConversationMemory) -> None:
    memory.add_turn(_TURN_A)
    memory.add_turn(_TURN_B)
    memory.reset()
    assert memory.turn_count == 0
    assert memory.get_history() == []


def test_max_turns_trims_oldest(memory: ConversationMemory) -> None:
    mem = ConversationMemory(max_turns=2)
    turn_0 = [{"role": "user", "content": "first"}]
    turn_1 = [{"role": "user", "content": "second"}]
    turn_2 = [{"role": "user", "content": "third"}]
    mem.add_turn(turn_0)
    mem.add_turn(turn_1)
    mem.add_turn(turn_2)
    # Only the last 2 turns should be kept
    assert mem.turn_count == 2
    assert mem.get_history() == turn_1 + turn_2


def test_disabled_memory_returns_empty() -> None:
    mem = ConversationMemory(enabled=False)
    mem.add_turn(_TURN_A)
    assert mem.turn_count == 0
    assert mem.get_history() == []


def test_disabled_property() -> None:
    assert ConversationMemory(enabled=False).enabled is False
    assert ConversationMemory(enabled=True).enabled is True


def test_add_empty_turn_is_ignored(memory: ConversationMemory) -> None:
    memory.add_turn([])
    assert memory.turn_count == 0


def test_max_turns_property() -> None:
    mem = ConversationMemory(max_turns=5)
    assert mem.max_turns == 5
