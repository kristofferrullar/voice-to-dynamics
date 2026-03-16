from src.agent.prompt_builder import build


def test_prompt_builds_without_error():
    prompt = build()
    assert isinstance(prompt, str)
    assert len(prompt) > 100


def test_prompt_contains_swedish_instruction():
    prompt = build()
    assert "Svenska" in prompt or "svenska" in prompt


def test_prompt_contains_entity_block():
    prompt = build()
    assert "opportunity" in prompt or "affärsmöjlighet" in prompt.lower()


def test_prompt_contains_tool_instructions():
    prompt = build()
    assert "query_template" in prompt or "template" in prompt.lower()


def test_prompt_is_cached():
    prompt1 = build()
    prompt2 = build()
    assert prompt1 is prompt2
