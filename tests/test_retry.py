import pytest

from ffai import retry_util
from ffai.retry_util import retry


@pytest.fixture
def sleeps(monkeypatch):
    recorded = []
    monkeypatch.setattr(retry_util.time, "sleep", recorded.append)
    return recorded


def test_returns_the_value_without_sleeping_when_it_works(sleeps):
    assert retry(lambda: 42) == 42
    assert sleeps == []


def test_succeeds_after_two_failures_with_linear_backoff(sleeps):
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("down")
        return "ok"

    assert retry(flaky) == "ok"
    assert sleeps == [2, 4]


def test_raises_the_last_error_after_all_tries(sleeps):
    def always_fails():
        raise ValueError("still broken")

    with pytest.raises(ValueError, match="still broken"):
        retry(always_fails, tries=3)
    assert len(sleeps) == 2  # no sleep after the final attempt
