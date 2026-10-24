import json

import pytest
import requests

from ffai import ai
from ffai.ai import AiSettings, Explanation, explain, template_text

RESULT = {
    "league": {"id": "1", "name": "L", "year": 2026, "week": 7},
    "team": {"id": 16, "name": "My Team"},
    "warnings": [
        {"level": "alert", "text": "Player A (RB) is OUT and is in your starting lineup."},
        {"level": "info", "text": "Player B (WR) is Questionable."},
    ],
    "pending": ["best lineup"],
}
SECRET = "sk-test-secret-123"


class FakeResponse:
    def __init__(self, status=200, body=None, text_ok=True):
        self.status_code = status
        self._body = body
        self._text_ok = text_ok

    def json(self):
        if not self._text_ok:
            raise ValueError("not json")
        return self._body


@pytest.fixture
def sent(monkeypatch):
    """Capture the HTTP call. `sent.reply` holds the answer of the fake server."""

    class Sent:
        calls = []
        reply = FakeResponse(200, {"content": [{"type": "text", "text": "Start B, bench A."}]})

    def fake_post(url, headers=None, json=None, timeout=None):
        Sent.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if isinstance(Sent.reply, Exception):
            raise Sent.reply
        return Sent.reply

    Sent.calls = []
    monkeypatch.setattr(ai.requests, "post", fake_post)
    return Sent


def _anthropic(model="claude-sonnet-5-5"):
    return AiSettings(provider="anthropic", api_key=SECRET, model=model)


# Template


def test_template_lists_alerts_but_not_info_lines():
    text = template_text(RESULT)
    assert "My Team" in text and "第7周" in text
    assert "Player A (RB) is OUT" in text
    assert "Questionable" not in text
    assert "best lineup" in text  # The text names the checks that are not done yet.


def test_template_for_a_clean_team():
    clean = {**RESULT, "warnings": [], "pending": []}
    assert "没有发现" in template_text(clean)


# No key: no network call


def test_without_a_key_the_template_is_used_and_nothing_is_sent(sent):
    out = explain(RESULT, AiSettings(model="claude-sonnet-5-5"))
    assert out.source == "template" and "key" in out.error
    assert sent.calls == []


def test_without_a_model_the_template_is_used(sent):
    assert explain(RESULT, AiSettings(api_key=SECRET)).source == "template"
    assert sent.calls == []


# Anthropic


def test_anthropic_request_carries_key_model_and_the_analysis(sent):
    out = explain(RESULT, _anthropic("claude-haiku-5-5"))
    assert out == Explanation("Start B, bench A.", "ai")
    call = sent.calls[0]
    assert call["url"] == "https://api.anthropic.com/v1/messages"
    assert call["headers"]["x-api-key"] == SECRET
    assert call["headers"]["anthropic-version"] == "2023-06-01"
    assert call["json"]["model"] == "claude-haiku-5-5"
    assert "Player A (RB)" in call["json"]["messages"][0]["content"]
    assert call["timeout"] > 0


def test_anthropic_text_blocks_are_joined(sent):
    sent.reply = FakeResponse(200, {"content": [{"type": "text", "text": "A"}, {"type": "tool_use"}, {"type": "text", "text": "B"}]})
    assert explain(RESULT, _anthropic()).text == "AB"


# OpenAI-compatible


def test_openai_compatible_request(sent):
    sent.reply = FakeResponse(200, {"choices": [{"message": {"content": "Use B."}}]})
    ai_settings = AiSettings(provider="openai", api_key=SECRET, model="deepseek-chat", base_url="https://api.deepseek.com/v1/")
    out = explain(RESULT, ai_settings)
    assert out == Explanation("Use B.", "ai")
    call = sent.calls[0]
    assert call["url"] == "https://api.deepseek.com/v1/chat/completions"  # The code handles the trailing slash.
    assert call["headers"]["Authorization"] == f"Bearer {SECRET}"
    assert call["json"]["model"] == "deepseek-chat"
    assert call["json"]["messages"][0]["role"] == "system"


def test_openai_default_base_url(sent):
    sent.reply = FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]})
    explain(RESULT, AiSettings(provider="openai", api_key=SECRET, model="m"))
    assert sent.calls[0]["url"] == "https://api.openai.com/v1/chat/completions"


# A failure falls back to the template and never leaks the key


def test_http_error_falls_back_and_scrubs_the_key(sent):
    sent.reply = FakeResponse(401, {"error": {"message": f"Incorrect API key provided: {SECRET}"}})
    out = explain(RESULT, _anthropic())
    assert out.source == "template"
    assert "401" in out.error
    assert SECRET not in out.error and SECRET not in out.text
    assert "***" in out.error


def test_network_error_falls_back(sent):
    sent.reply = requests.ConnectionError(f"failed to reach host with {SECRET}")
    out = explain(RESULT, _anthropic())
    assert out.source == "template"
    assert SECRET not in out.error


def test_reply_that_is_not_json_falls_back(sent):
    sent.reply = FakeResponse(200, text_ok=False)
    assert explain(RESULT, _anthropic()).source == "template"


def test_unexpected_reply_shape_falls_back(sent):
    sent.reply = FakeResponse(200, {"unexpected": True})
    assert explain(RESULT, _anthropic()).source == "template"


def test_empty_model_answer_falls_back(sent):
    sent.reply = FakeResponse(200, {"content": [{"type": "text", "text": "  "}]})
    assert explain(RESULT, _anthropic()).source == "template"


def test_unknown_provider_falls_back(sent):
    out = explain(RESULT, AiSettings(provider="mystery", api_key=SECRET, model="m"))
    assert out.source == "template" and "mystery" in out.error
    assert sent.calls == []


def test_the_key_is_not_written_to_the_log_on_failure(sent):
    from loguru import logger

    lines = []
    sink = logger.add(lines.append, level="DEBUG")
    try:
        sent.reply = FakeResponse(401, {"error": {"message": f"bad key {SECRET}"}})
        explain(RESULT, _anthropic())
    finally:
        logger.remove(sink)
    assert lines and not any(SECRET in str(line) for line in lines)


# Settings from the panel


def test_panel_values_win_over_env(monkeypatch):
    monkeypatch.setattr(ai.settings, "ai_api_key", "env-key")
    monkeypatch.setattr(ai.settings, "ai_model", "env-model")
    monkeypatch.setattr(ai.settings, "ai_provider", "anthropic")
    monkeypatch.setattr(ai.settings, "ai_base_url", "")
    got = AiSettings.from_request({"api_key": "panel-key", "model": "panel-model", "provider": "OpenAI"})
    assert (got.api_key, got.model, got.provider) == ("panel-key", "panel-model", "openai")


def test_empty_panel_fields_fall_back_to_env(monkeypatch):
    monkeypatch.setattr(ai.settings, "ai_api_key", "env-key")
    monkeypatch.setattr(ai.settings, "ai_model", "env-model")
    monkeypatch.setattr(ai.settings, "ai_provider", "anthropic")
    monkeypatch.setattr(ai.settings, "ai_base_url", "")
    got = AiSettings.from_request({"api_key": "  ", "model": ""})
    assert (got.api_key, got.model) == ("env-key", "env-model")


def test_garbage_settings_do_not_crash(monkeypatch):
    monkeypatch.setattr(ai.settings, "ai_api_key", "")
    monkeypatch.setattr(ai.settings, "ai_model", "")
    assert AiSettings.from_request(None).api_key == ""
    assert AiSettings.from_request({"api_key": 5}).api_key == ""
    json.dumps(AiSettings.from_request("nope").__dict__)
