import pytest

from ffai.config import ConfigError, Settings

# Every variable a test below reads. A developer's real .env is loaded at
# import, so each test clears what it asserts on instead of trusting the shell.
_CHANNEL_VARS = [
    "EMAIL_FROM", "EMAIL_PASSWORD", "EMAIL_TO", "NTFY_TOPIC",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "DISCORD_WEBHOOK_URL",
]
_ESPN_VARS = ["ESPN_LEAGUE_IDS", "ESPN_S2", "ESPN_SWID"]


def _clear(monkeypatch, names):
    for name in names:
        monkeypatch.delenv(name, raising=False)


def test_defaults_when_nothing_is_set(monkeypatch):
    _clear(monkeypatch, _CHANNEL_VARS + ["ESPN_YEAR", "QUIET_HOURS", "LINEUP_MIN_GAIN"])
    s = Settings()
    assert s.espn_year == 2026
    assert s.quiet_hours == (23, 8)
    assert s.lineup_min_gain == 1.0
    assert s.configured_channels() == []


def test_empty_value_counts_as_not_set(monkeypatch):
    monkeypatch.setenv("ESPN_YEAR", "")
    assert Settings().espn_year == 2026


def test_a_channel_needs_all_of_its_settings(monkeypatch):
    _clear(monkeypatch, _CHANNEL_VARS)
    monkeypatch.setenv("EMAIL_FROM", "a@example.com")
    assert Settings().configured_channels() == []  # password and recipient missing
    monkeypatch.setenv("EMAIL_PASSWORD", "app-password")
    monkeypatch.setenv("EMAIL_TO", "b@example.com")
    monkeypatch.setenv("NTFY_TOPIC", "some-long-random-topic")
    assert Settings().configured_channels() == ["email", "ntfy"]


def test_bad_quiet_hours_are_rejected(monkeypatch):
    monkeypatch.setenv("QUIET_HOURS", "late")
    with pytest.raises(ConfigError):
        Settings()
    monkeypatch.setenv("QUIET_HOURS", "25-8")
    with pytest.raises(ConfigError):
        Settings()


def test_bad_number_is_rejected(monkeypatch):
    monkeypatch.setenv("FA_MIN_GAIN", "a lot")
    with pytest.raises(ConfigError):
        Settings()


def test_no_leagues_by_default(monkeypatch):
    _clear(monkeypatch, ["ESPN_LEAGUE_IDS", "ESPN_TEAM_IDS"])
    s = Settings()
    assert s.espn_league_ids == ()
    assert s.team_id_for("1669256142") == ""


def test_league_ids_are_split_trimmed_and_deduplicated(monkeypatch):
    monkeypatch.setenv("ESPN_LEAGUE_IDS", " 1669256142 , 2222222 ,1669256142,")
    assert Settings().espn_league_ids == ("1669256142", "2222222")


def test_league_ids_must_be_numbers(monkeypatch):
    monkeypatch.setenv("ESPN_LEAGUE_IDS", "1669256142,my-league")
    with pytest.raises(ConfigError):
        Settings()


def test_team_ids_are_read_per_league(monkeypatch):
    monkeypatch.setenv("ESPN_LEAGUE_IDS", "1669256142,2222222")
    monkeypatch.setenv("ESPN_TEAM_IDS", "1669256142:16")
    s = Settings()
    assert s.team_id_for("1669256142") == "16"
    assert s.team_id_for("2222222") == ""  # detect from SWID


def test_team_ids_must_belong_to_a_configured_league(monkeypatch):
    monkeypatch.setenv("ESPN_LEAGUE_IDS", "1669256142")
    monkeypatch.setenv("ESPN_TEAM_IDS", "9999999:3")
    with pytest.raises(ConfigError):
        Settings()


def test_bad_team_ids_format_is_rejected(monkeypatch):
    monkeypatch.setenv("ESPN_LEAGUE_IDS", "1669256142")
    monkeypatch.setenv("ESPN_TEAM_IDS", "16")
    with pytest.raises(ConfigError):
        Settings()


def test_require_espn_lists_every_missing_variable(monkeypatch):
    _clear(monkeypatch, _ESPN_VARS)
    with pytest.raises(ConfigError) as err:
        Settings().require_espn()
    for name in _ESPN_VARS:
        assert name in str(err.value)


def test_secrets_never_appear_in_repr(monkeypatch):
    monkeypatch.setenv("ESPN_S2", "super-secret-cookie")
    monkeypatch.setenv("AI_API_KEY", "sk-secret")
    text = repr(Settings())
    assert "super-secret-cookie" not in text
    assert "sk-secret" not in text
