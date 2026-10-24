# ==============================================================================
# ai.py - optional LLM explanation of alerts   [STUB - SPEC step 6]
#
# Anthropic Messages API or any OpenAI-compatible endpoint, both over plain
# HTTP (SPEC 7). Rules: only called for NEW alerts, numbers are copied from the
# alert payload and never invented, and ANY failure falls back to
# template_text() so an AI error can never block a notification.
# ==============================================================================
from ffai.models import Alert


def template_text(alert: Alert) -> str:
    """Plain, no-AI message body. Used without an API key and as the fallback."""
    raise NotImplementedError("SPEC section 7")


def explain(alerts: list[Alert]) -> str:
    """Short Chinese text for a phone notification. Falls back to template_text."""
    raise NotImplementedError("SPEC section 7")
