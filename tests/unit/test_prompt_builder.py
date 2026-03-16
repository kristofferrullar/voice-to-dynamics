"""Tests for the dynamic prompt builder."""
from src.agent.prompt_builder import build, invalidate_cache

_GITHUB_SUMMARY = {
    "name": "github",
    "description": "GitHub — search repos, manage issues",
    "tools": ["search_repositories", "get_file_contents", "create_issue"],
}

_DATAVERSE_SUMMARY = {
    "name": "dataverse",
    "description": "Microsoft Dataverse / Dynamics 365",
    "tools": ["query_records_tool", "count_records_tool", "create_record_tool"],
}


def test_prompt_builds_without_error_no_servers():
    prompt = build([])
    assert isinstance(prompt, str)
    assert len(prompt) > 100
    assert "No MCP servers" in prompt


def test_prompt_builds_with_servers():
    prompt = build([_GITHUB_SUMMARY, _DATAVERSE_SUMMARY])
    assert isinstance(prompt, str)
    assert len(prompt) > 100


def test_prompt_contains_swedish_language_policy():
    prompt = build([_GITHUB_SUMMARY])
    assert "Swedish" in prompt or "svenska" in prompt.lower()


def test_prompt_contains_server_name():
    prompt = build([_GITHUB_SUMMARY])
    assert "github" in prompt


def test_prompt_contains_tool_preview():
    prompt = build([_GITHUB_SUMMARY])
    assert "search_repositories" in prompt


def test_prompt_shows_multiple_servers():
    prompt = build([_GITHUB_SUMMARY, _DATAVERSE_SUMMARY])
    assert "github" in prompt
    assert "dataverse" in prompt


def test_prompt_is_different_for_different_summaries():
    prompt_a = build([_GITHUB_SUMMARY])
    prompt_b = build([_DATAVERSE_SUMMARY])
    assert prompt_a != prompt_b


def test_prompt_dataverse_not_configured_section(monkeypatch):
    """When Dataverse creds are absent the prompt should say 'Not configured'."""
    from config.settings import Settings
    monkeypatch.setattr(
        "src.agent.prompt_builder.get_settings",
        lambda: Settings(
            azure_tenant_id="",
            azure_client_id="",
            azure_client_secret="",
            dataverse_environment_url="",
            anthropic_api_key="x",
            azure_speech_key="x",
        ),
    )
    prompt = build([_GITHUB_SUMMARY])
    assert "Not configured" in prompt


def test_invalidate_cache_is_noop():
    """invalidate_cache() must not raise and must remain backward-compatible."""
    invalidate_cache()  # no-op since v0.2
    prompt = build([_GITHUB_SUMMARY])
    assert isinstance(prompt, str)
