# ==============================================================================
# ai.py: optional LLM explanation of an analysis result (SPEC section 7)
#
# The numbers always come from pipeline.analyze().
# The model only turns the numbers into short advice.
# Rules:
#   * ANY failure falls back to template_text(), so the caller always gets text.
#   * The API key arrives with each request from the panel.
#     The service never stores the key and never logs it.
#     The service removes the key from every error message.
#   * The code uses plain HTTP with a timeout. It uses no SDK.
#
# The code sends only the basic request fields (model, max_tokens, system, messages).
# It does not depend on newer API options.
# config.py reads AI_EFFORT, but the code does not send it yet.
# Check the current Anthropic docs before you add it.
# ==============================================================================
import json
from dataclasses import dataclass

import requests
from loguru import logger

from ffai.config import settings

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"
TIMEOUT_SECONDS = 45
MAX_TOKENS = 700

SYSTEM_PROMPT = (
    "You are a fantasy football assistant. You get an analysis of one fantasy team as JSON. "
    "Write in Chinese. Keep it short, because it is read on a phone. "
    "Put the most urgent action first, and give one short reason for each suggestion. "
    "Copy every number exactly as given. Never invent injuries, news or numbers that are not in the JSON. "
    "If the JSON lists items under 'pending', say that those checks have not been done yet."
)


@dataclass(frozen=True)
class AiSettings:
    provider: str = "anthropic"  # "anthropic" or "openai". "openai" covers any OpenAI-compatible endpoint.
    api_key: str = ""
    model: str = ""
    base_url: str = ""

    @classmethod
    def from_request(cls, raw: dict | None) -> "AiSettings":
        """Build the settings from the request.

        A value from the panel wins. An empty field falls back to AI_* in .env.
        """
        raw = raw if isinstance(raw, dict) else {}

        def pick(name: str, fallback: str) -> str:
            value = raw.get(name)
            return value.strip() if isinstance(value, str) and value.strip() else fallback

        return cls(
            provider=pick("provider", settings.ai_provider or "anthropic").lower(),
            api_key=pick("api_key", settings.ai_api_key),
            model=pick("model", settings.ai_model),
            base_url=pick("base_url", settings.ai_base_url),
        )


@dataclass(frozen=True)
class Explanation:
    text: str
    source: str  # "ai" or "template"
    error: str = ""  # Why the code used the template. It is safe to show, because the code removed the key.


class AiError(Exception):
    pass


def template_text(result: dict) -> str:
    """Return a plain Chinese summary without AI. The code uses it without a key and as the fallback."""
    lines = [f"{result['team']['name']} - 第{result['league']['week']}周"]
    alerts = [w for w in result.get("warnings", []) if w["level"] != "info"]
    if alerts:
        lines.append("需要处理:")
        lines += [f"- {w['text']}" for w in alerts]
    else:
        lines.append("没有发现 OUT、轮空或空位的问题。")
    if result.get("pending"):
        lines.append("还没检查: " + ", ".join(result["pending"]))
    return "\n".join(lines)


def explain(result: dict, ai: AiSettings) -> Explanation:
    if not ai.api_key or not ai.model:
        return Explanation(template_text(result), "template", "No AI key or model is set.")
    try:
        text = _call(result, ai).strip()
        if not text:
            raise AiError("the model returned no text")
        return Explanation(text, "ai")
    except Exception as e:  # noqa: BLE001
        # An AI failure must never block the answer.
        message = _scrub(str(e), ai.api_key)
        logger.warning(f"AI explanation failed, using the template: {message}")
        return Explanation(template_text(result), "template", message)


def _scrub(text: str, secret: str) -> str:
    return text.replace(secret, "***") if secret else text


def _call(result: dict, ai: AiSettings) -> str:
    user_message = "Analysis:\n" + json.dumps(result, ensure_ascii=False)
    if ai.provider == "anthropic":
        return _call_anthropic(user_message, ai)
    if ai.provider == "openai":
        return _call_openai(user_message, ai)
    raise AiError(f"unknown AI provider '{ai.provider}' (use 'anthropic' or 'openai')")


def _post(url: str, headers: dict, body: dict, key: str) -> dict:
    try:
        response = requests.post(url, headers=headers, json=body, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as e:
        raise AiError(f"could not reach the AI service: {type(e).__name__}") from None
    if response.status_code >= 400:
        detail = ""
        try:
            detail = response.json().get("error", {})
            detail = detail.get("message", "") if isinstance(detail, dict) else str(detail)
        except ValueError:
            pass
        raise AiError(f"AI service answered {response.status_code}: {_scrub(detail, key)[:200]}")
    try:
        return response.json()
    except ValueError:
        raise AiError("the AI service sent a reply that is not JSON") from None


def _call_anthropic(user_message: str, ai: AiSettings) -> str:
    data = _post(
        ANTHROPIC_URL,  # Only OpenAI-compatible services use base_url.
        {"x-api-key": ai.api_key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"},
        {
            "model": ai.model or DEFAULT_ANTHROPIC_MODEL,
            "max_tokens": MAX_TOKENS,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_message}],
        },
        ai.api_key,
    )
    try:
        return "".join(block.get("text", "") for block in data["content"] if block.get("type") == "text")
    except (KeyError, TypeError, AttributeError):
        raise AiError("unexpected reply format from the Anthropic API") from None


def _call_openai(user_message: str, ai: AiSettings) -> str:
    base = (ai.base_url or OPENAI_DEFAULT_BASE_URL).rstrip("/")
    data = _post(
        f"{base}/chat/completions",
        {"Authorization": f"Bearer {ai.api_key}", "content-type": "application/json"},
        {
            "model": ai.model,
            # The request has no max_tokens. Newer OpenAI models renamed it.
            # Other OpenAI-compatible services differ. The prompt asks for a short answer.
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_message}],
        },
        ai.api_key,
    )
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise AiError("unexpected reply format from the AI service") from None
