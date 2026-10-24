import pytest

from ffai import store
from ffai.config import settings
from ffai.models import LINEUP, Alert


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", tmp_path / "test.db")


def _alert(key="lineup:7:swap-a"):
    return Alert(kind=LINEUP, key=key, title="Start X, bench Y", body="...", week=7)


def test_unknown_alert_is_not_sent():
    assert store.is_sent("lineup:7:swap-a") is False


def test_mark_sent_returns_true_only_the_first_time():
    assert store.mark_sent(_alert()) is True
    assert store.mark_sent(_alert()) is False


def test_is_sent_is_read_only_until_mark_sent():
    # The gate must not record anything: a failed notification has to be
    # retried on the next check.
    assert store.is_sent("lineup:7:swap-a") is False
    assert store.is_sent("lineup:7:swap-a") is False
    store.mark_sent(_alert())
    assert store.is_sent("lineup:7:swap-a") is True


def test_different_keys_are_independent():
    store.mark_sent(_alert("lineup:7:swap-a"))
    assert store.is_sent("lineup:7:swap-b") is False


def test_kv_returns_default_then_stored_value_then_overwrite():
    assert store.get_kv("cookie_expired_reported") is None
    assert store.get_kv("cookie_expired_reported", "no") == "no"
    store.set_kv("cookie_expired_reported", "yes")
    assert store.get_kv("cookie_expired_reported") == "yes"
    store.set_kv("cookie_expired_reported", "no")
    assert store.get_kv("cookie_expired_reported") == "no"


def test_database_file_is_created_on_first_use(tmp_path):
    assert not (tmp_path / "test.db").exists()
    store.is_sent("anything")
    assert (tmp_path / "test.db").exists()
