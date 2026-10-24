# ==============================================================================
# notify.py: push channels (SPEC section 8)
#
# stock-ai has only an email notifier and no shared interface.
# Here every channel implements `Channel`.
# `Notifier` sends to all configured channels.
#
# Failure rules (copied from EmailNotifier in stock-ai):
#   * A channel never raises. It logs the problem and returns False.
#   * One failing channel must not stop the other channels.
#   * Notifier.send returns True when ANY channel delivered the message.
#     Only then does the caller call store.mark_sent.
#     When all channels fail, the next check sends the alert again.
# ==============================================================================
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage

from loguru import logger

from ffai.config import settings
from ffai.models import Alert
from ffai.retry_util import retry


class Channel(ABC):
    name: str

    @abstractmethod
    def is_configured(self) -> bool:
        """True when the channel has every setting that it needs."""

    @abstractmethod
    def send(self, title: str, body: str, urgent: bool = False) -> bool:
        """Deliver one message. Return False on failure. Never raise."""


class EmailChannel(Channel):
    name = "email"
    smtp_host = "smtp.gmail.com"
    smtp_port = 465

    def __init__(self):
        self.email_from = settings.email_from
        self.email_password = settings.email_password  # Gmail app password
        self.email_to = settings.email_to

    def is_configured(self) -> bool:
        return bool(self.email_from and self.email_password and self.email_to)

    def send(self, title: str, body: str, urgent: bool = False) -> bool:
        msg = EmailMessage()
        msg["Subject"] = f"[ffai] {title}"
        msg["From"] = self.email_from
        msg["To"] = self.email_to
        if urgent:
            msg["X-Priority"] = "1"
        msg.set_content(body)

        def _do_send():
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
                server.login(self.email_from, self.email_password)
                server.send_message(msg)

        try:
            retry(_do_send, label=f"email '{title}'")
            logger.info(f"Email sent to {self.email_to}: {title}")
            return True
        except Exception as e:  # noqa: BLE001
            # A failed email must not crash the run.
            logger.error(f"Failed to send email after retries - {e}")
            return False


# The channels below are not built yet (SPEC section 8).
# They report their configuration state, so `configured_channels` is correct.
# Their send method raises NotImplementedError.


class NtfyChannel(Channel):
    """TODO: publish as JSON, so Chinese text displays correctly (SPEC 8)."""

    name = "ntfy"

    def is_configured(self) -> bool:
        return bool(settings.ntfy_topic)

    def send(self, title: str, body: str, urgent: bool = False) -> bool:
        raise NotImplementedError("ntfy channel is not written yet (SPEC section 8)")


class TelegramChannel(Channel):
    name = "telegram"

    def is_configured(self) -> bool:
        return bool(settings.telegram_bot_token and settings.telegram_chat_id)

    def send(self, title: str, body: str, urgent: bool = False) -> bool:
        raise NotImplementedError("telegram channel is not written yet (SPEC section 8)")


class DiscordChannel(Channel):
    name = "discord"

    def is_configured(self) -> bool:
        return bool(settings.discord_webhook_url)

    def send(self, title: str, body: str, urgent: bool = False) -> bool:
        raise NotImplementedError("discord channel is not written yet (SPEC section 8)")


def build_channels() -> list[Channel]:
    candidates = [EmailChannel(), NtfyChannel(), TelegramChannel(), DiscordChannel()]
    return [c for c in candidates if c.is_configured()]


class Notifier:
    def __init__(self, channels: list[Channel] | None = None):
        # `channels` lets a test give fake channels. stock-ai does the same with `translate_call`.
        self.channels = build_channels() if channels is None else channels

    def send(self, alert: Alert) -> bool:
        title = f"[{alert.league_name}] {alert.title}" if alert.league_name else alert.title
        return self.send_text(title, alert.body, alert.urgent)

    def send_text(self, title: str, body: str, urgent: bool = False) -> bool:
        if not self.channels:
            logger.warning("No notification channel is configured - nothing was sent")
            return False
        delivered = False
        for channel in self.channels:
            try:
                if channel.send(title, body, urgent):
                    delivered = True
                else:
                    logger.warning(f"{channel.name} did not deliver: {title}")
            except Exception:  # noqa: BLE001
                # A failure in one channel must not stop the other channels.
                logger.exception(f"{channel.name} raised while sending: {title}")
        return delivered
