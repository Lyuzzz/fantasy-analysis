# ==============================================================================
# config.py: settings that the program reads once from the environment and .env
#
# This file follows core/config.py in stock-ai. It builds one `settings` object
# when Python imports the module.
# An import must never fail because an optional secret is missing. Tests and CI
# import ffai without a .env file.
# A command that needs a secret calls `settings.require_espn()`. The error then
# appears in the right place with a clear message.
# ==============================================================================
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

# load_dotenv does not replace a variable that is already set.
# A real environment variable (Docker env_file, CI) therefore wins over a local .env.
load_dotenv(ROOT / ".env")


class ConfigError(Exception):
    """A setting is missing, or its value is not usable."""


def _str(name: str, default: str = "") -> str:
    # `or default` makes an empty value (KEY= in .env.example) mean "not set".
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
    """'23-8' becomes (23, 8). The quiet time starts at 23:00 and ends at 08:00 local time."""
    try:
        start_s, end_s = raw.split("-")
        start, end = int(start_s), int(end_s)
    except ValueError:
        raise ConfigError(f"QUIET_HOURS must look like '23-8', got {raw!r}") from None
    if not (0 <= start <= 23 and 0 <= end <= 23):
        raise ConfigError(f"QUIET_HOURS hours must be 0-23, got {raw!r}")
    return start, end


def _parse_league_ids(raw: str) -> tuple[str, ...]:
    """'111, 222' becomes ('111', '222'). The function keeps the order and drops duplicates."""
    ids: list[str] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit():
            raise ConfigError(f"ESPN_LEAGUE_IDS must be numbers separated by commas, got {part!r}")
        if part not in ids:
            ids.append(part)
    return tuple(ids)


def _parse_team_ids(raw: str, league_ids: tuple[str, ...]) -> dict[str, str]:
    """'111:16, 222:3' becomes {'111': '16', '222': '3'}."""
    mapping: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        league_id, sep, team_id = part.partition(":")
        if not sep or not league_id.strip().isdigit() or not team_id.strip().isdigit():
            raise ConfigError(f"ESPN_TEAM_IDS must look like '111:16,222:3', got {part!r}")
        if league_id.strip() not in league_ids:
            raise ConfigError(f"ESPN_TEAM_IDS names league {league_id.strip()}, which is not in ESPN_LEAGUE_IDS")
        mapping[league_id.strip()] = team_id.strip()
    return mapping


class Settings:
    def __init__(self):
        # ESPN settings.
        # One account can play in several leagues.
        # The two cookies belong to the account, so every league uses the same two cookies.
        self.espn_league_ids = _parse_league_ids(_str("ESPN_LEAGUE_IDS"))
        self.espn_year = _int("ESPN_YEAR", 2026)
        self.espn_s2 = _str("ESPN_S2")
        self.espn_swid = _str("ESPN_SWID")
        # This value is normally empty. The team of the user is the team whose owners include the SWID.
        # Set a team id for a league only when that detection fails.
        self.espn_team_ids = _parse_team_ids(_str("ESPN_TEAM_IDS"), self.espn_league_ids)

        # Time settings.
        # The program uses UTC inside.
        # It uses the time zone only to show times and to decide the quiet hours.
        self.timezone = _str("TIMEZONE", "America/Denver")
        self.quiet_hours = _parse_quiet_hours(_str("QUIET_HOURS", "23-8"))
        self.active_lead_hours = _float("ACTIVE_LEAD_HOURS", 2.0)
        self.check_interval_seconds = _int("CHECK_INTERVAL_SECONDS", 600)

        # Analysis settings (SPEC sections 5.1 and 5.4).
        self.doubtful_discount = _float("DOUBTFUL_DISCOUNT", 0.25)
        self.questionable_discount = _float("QUESTIONABLE_DISCOUNT", 0.9)
        self.lineup_min_gain = _float("LINEUP_MIN_GAIN", 1.0)
        self.fa_min_gain = _float("FA_MIN_GAIN", 1.0)
        self.fa_min_week_gain = _float("FA_MIN_WEEK_GAIN", 3.0)
        # Version 2 settings (trades). They exist now, so .env.example is complete.
        self.trade_min_gain = _float("TRADE_MIN_GAIN", 1.0)
        self.trade_min_partner_gain = _float("TRADE_MIN_PARTNER_GAIN", 0.3)

        # AI settings (optional).
        self.ai_provider = _str("AI_PROVIDER", "anthropic").lower()
        self.ai_api_key = _str("AI_API_KEY")
        self.ai_model = _str("AI_MODEL")
        self.ai_base_url = _str("AI_BASE_URL")
        self.ai_effort = _str("AI_EFFORT", "low")

        # Notification channels.
        self.email_from = _str("EMAIL_FROM")
        self.email_password = _str("EMAIL_PASSWORD")
        self.email_to = _str("EMAIL_TO")
        self.ntfy_topic = _str("NTFY_TOPIC")
        self.telegram_bot_token = _str("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = _str("TELEGRAM_CHAT_ID")
        self.discord_webhook_url = _str("DISCORD_WEBHOOK_URL")
        self.healthcheck_url = _str("HEALTHCHECK_URL")

        # Service for the Chrome extension. It listens on 127.0.0.1 only.
        self.service_port = _int("SERVICE_PORT", 8765)
        # Optional. The service accepts only this extension id.
        # An empty value accepts any chrome-extension:// origin.
        self.extension_id = _str("EXTENSION_ID")

        # Storage.
        # Docker sets FFAI_DB_PATH to /data/ffai.db. The tests set it to a temporary file.
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

    def team_id_for(self, league_id: str) -> str:
        """The manual team id for one league. An empty string means: detect the team from the SWID."""
        return self.espn_team_ids.get(league_id, "")

    def require_espn(self) -> None:
        """Raise ConfigError when the ESPN login settings are incomplete."""
        required = {
            "ESPN_LEAGUE_IDS": self.espn_league_ids,
            "ESPN_S2": self.espn_s2,
            "ESPN_SWID": self.espn_swid,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ConfigError("missing ESPN settings in .env: " + ", ".join(missing))

    def __repr__(self) -> str:
        # espn_s2 is a login credential.
        # This method never prints it, so a log line cannot leak it by accident.
        # An example is logger.debug(settings).
        leagues = ",".join(self.espn_league_ids) or "-"
        return f"<Settings leagues={leagues} year={self.espn_year} (secrets hidden)>"


settings = Settings()
