# ==============================================================================
# config.py - settings, read once from the environment / .env
#
# Same idea as stock-ai's core/config.py: one module-level `settings` object,
# built at import time. Importing this module must NEVER fail because an
# optional secret is missing (tests and CI import ffai without a .env).
# Commands that really need a secret call `settings.require_espn()` instead,
# so the error shows up at the right place with a clear message.
# ==============================================================================
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

# load_dotenv does not override variables that are already set, so a real
# environment variable (Docker env_file, CI) always wins over a local .env.
load_dotenv(ROOT / ".env")


class ConfigError(Exception):
    """A setting is missing or has a value we cannot use."""


def _str(name: str, default: str = "") -> str:
    # `or default` so an empty value (KEY= in .env.example) means "not set".
    return (os.getenv(name) or default).strip()


def _float(name: str, default: float) -> float:
    raw = _str(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None


def _int(name: str, default: int) -> int:
    raw = _str(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}") from None


def _parse_quiet_hours(raw: str) -> tuple[int, int]:
    """'23-8' -> (23, 8): quiet from 23:00 until 08:00 local time."""
    try:
        start_s, end_s = raw.split("-")
        start, end = int(start_s), int(end_s)
    except ValueError:
        raise ConfigError(f"QUIET_HOURS must look like '23-8', got {raw!r}") from None
    if not (0 <= start <= 23 and 0 <= end <= 23):
        raise ConfigError(f"QUIET_HOURS hours must be 0-23, got {raw!r}")
    return start, end


class Settings:
    def __init__(self):
        # --- ESPN ---
        self.espn_league_id = _str("ESPN_LEAGUE_ID")
        self.espn_year = _int("ESPN_YEAR", 2026)
        self.espn_s2 = _str("ESPN_S2")
        self.espn_swid = _str("ESPN_SWID")
        self.espn_team_id = _str("ESPN_TEAM_ID")  # empty = detect from SWID

        # --- time ---
        # Everything internal is UTC. The zone is only used to show times and
        # to decide quiet hours.
        self.timezone = _str("TIMEZONE", "America/Denver")
        self.quiet_hours = _parse_quiet_hours(_str("QUIET_HOURS", "23-8"))
        self.active_lead_hours = _float("ACTIVE_LEAD_HOURS", 2.0)
        self.check_interval_seconds = _int("CHECK_INTERVAL_SECONDS", 600)

        # --- analysis knobs (SPEC sections 5.1 and 5.4) ---
        self.doubtful_discount = _float("DOUBTFUL_DISCOUNT", 0.25)
        self.questionable_discount = _float("QUESTIONABLE_DISCOUNT", 0.9)
        self.lineup_min_gain = _float("LINEUP_MIN_GAIN", 1.0)
        self.fa_min_gain = _float("FA_MIN_GAIN", 1.0)
        self.fa_min_week_gain = _float("FA_MIN_WEEK_GAIN", 3.0)
        # v2 (trades), kept here so .env.example is complete from day one.
        self.trade_min_gain = _float("TRADE_MIN_GAIN", 1.0)
        self.trade_min_partner_gain = _float("TRADE_MIN_PARTNER_GAIN", 0.3)

        # --- AI (optional) ---
        self.ai_provider = _str("AI_PROVIDER", "anthropic").lower()
        self.ai_api_key = _str("AI_API_KEY")
        self.ai_model = _str("AI_MODEL")
        self.ai_base_url = _str("AI_BASE_URL")
        self.ai_effort = _str("AI_EFFORT", "low")

        # --- notification channels ---
        self.email_from = _str("EMAIL_FROM")
        self.email_password = _str("EMAIL_PASSWORD")
        self.email_to = _str("EMAIL_TO")
        self.ntfy_topic = _str("NTFY_TOPIC")
        self.telegram_bot_token = _str("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = _str("TELEGRAM_CHAT_ID")
        self.discord_webhook_url = _str("DISCORD_WEBHOOK_URL")
        self.healthcheck_url = _str("HEALTHCHECK_URL")

        # --- storage ---
        # FFAI_DB_PATH is overridden by Docker (/data/ffai.db) and by tests.
        self.db_path = Path(_str("FFAI_DB_PATH") or ROOT / "ffai.db")

    def configured_channels(self) -> list[str]:
        """Names of the notification channels that have complete settings."""
        names = []
        if self.email_from and self.email_password and self.email_to:
            names.append("email")
        if self.ntfy_topic:
            names.append("ntfy")
        if self.telegram_bot_token and self.telegram_chat_id:
            names.append("telegram")
        if self.discord_webhook_url:
            names.append("discord")
        return names

    def require_espn(self) -> None:
        """Raise ConfigError if the ESPN login settings are incomplete."""
        required = {
            "ESPN_LEAGUE_ID": self.espn_league_id,
            "ESPN_S2": self.espn_s2,
            "ESPN_SWID": self.espn_swid,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ConfigError("missing ESPN settings in .env: " + ", ".join(missing))

    def __repr__(self) -> str:
        # espn_s2 is a login credential. Never let it reach a log line by
        # accident (for example through logger.debug(settings)).
        return f"<Settings league={self.espn_league_id or '-'} year={self.espn_year} (secrets hidden)>"


settings = Settings()
