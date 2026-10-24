import pytest

from ffai import cli
from ffai.cli import EXIT_FAILED, EXIT_NOT_IMPLEMENTED, EXIT_OK, main


@pytest.mark.parametrize("command", ["check", "report", "teams", "demo"])
def test_unbuilt_commands_exit_with_not_implemented(command):
    assert main([command]) == EXIT_NOT_IMPLEMENTED


def test_check_accepts_dry_run_flag():
    assert main(["check", "--dry-run"]) == EXIT_NOT_IMPLEMENTED


def test_a_command_is_required():
    with pytest.raises(SystemExit) as err:
        main([])
    assert err.value.code == 2


class FakeNotifier:
    def __init__(self, channels, ok):
        self.channels = channels
        self._ok = ok

    def send_text(self, title, body, urgent=False):
        return self._ok


class _Named:
    name = "email"


def test_test_notify_without_channels_is_a_warning_not_an_error(monkeypatch):
    monkeypatch.setattr(cli, "Notifier", lambda: FakeNotifier([], True))
    assert main(["test-notify"]) == EXIT_OK


def test_test_notify_fails_when_nothing_was_delivered(monkeypatch):
    monkeypatch.setattr(cli, "Notifier", lambda: FakeNotifier([_Named()], False))
    assert main(["test-notify"]) == EXIT_FAILED


def test_test_notify_succeeds_when_delivered(monkeypatch):
    monkeypatch.setattr(cli, "Notifier", lambda: FakeNotifier([_Named()], True))
    assert main(["test-notify"]) == EXIT_OK


def test_run_stops_at_once_while_check_is_a_stub(monkeypatch):
    slept = []
    monkeypatch.setattr(cli.time, "sleep", slept.append)
    assert main(["run"]) == EXIT_NOT_IMPLEMENTED
    assert slept == []


def test_run_keeps_looping_and_survives_a_failed_cycle(monkeypatch):
    results = iter([0, RuntimeError("one bad cycle"), 0])
    sleeps = []

    def fake_check(args):
        item = next(results)
        if isinstance(item, Exception):
            raise item
        return item

    def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise KeyboardInterrupt  # This is how a user stops `run`.

    monkeypatch.setattr(cli, "cmd_check", fake_check)
    monkeypatch.setattr(cli.time, "sleep", fake_sleep)
    assert main(["run"]) == EXIT_OK
    assert len(sleeps) == 3  # The exception in cycle 2 did not end the loop.
