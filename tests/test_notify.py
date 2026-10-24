import pytest

from ffai import notify, retry_util
from ffai.models import LINEUP, Alert
from ffai.notify import Channel, EmailChannel, Notifier


class FakeChannel(Channel):
    def __init__(self, name, result=True, raises=False):
        self.name = name
        self.result = result
        self.raises = raises
        self.sent = []

    def is_configured(self):
        return True

    def send(self, title, body, urgent=False):
        if self.raises:
            raise RuntimeError("boom")
        self.sent.append((title, body, urgent))
        return self.result


def _alert(urgent=False):
    return Alert(kind=LINEUP, key="k", title="T", body="B", urgent=urgent)


def test_no_channels_means_not_delivered():
    assert Notifier(channels=[]).send(_alert()) is False


def test_delivered_when_at_least_one_channel_works():
    bad, good = FakeChannel("a", result=False), FakeChannel("b")
    assert Notifier(channels=[bad, good]).send(_alert()) is True
    assert good.sent == [("T", "B", False)]


def test_not_delivered_when_every_channel_fails():
    channels = [FakeChannel("a", result=False), FakeChannel("b", raises=True)]
    assert Notifier(channels=channels).send(_alert()) is False


def test_a_raising_channel_does_not_stop_the_others():
    boom, good = FakeChannel("a", raises=True), FakeChannel("b")
    assert Notifier(channels=[boom, good]).send(_alert()) is True
    assert len(good.sent) == 1


def test_league_name_is_added_to_the_title():
    ch = FakeChannel("a")
    Notifier(channels=[ch]).send(Alert(kind=LINEUP, key="k", title="Start X", body="B", league_name="Sunday League"))
    assert ch.sent[0][0] == "[Sunday League] Start X"


def test_account_level_alert_has_no_league_prefix():
    ch = FakeChannel("a")
    Notifier(channels=[ch]).send(_alert())
    assert ch.sent[0][0] == "T"


def test_urgent_flag_is_passed_to_the_channel():
    ch = FakeChannel("a")
    Notifier(channels=[ch]).send(_alert(urgent=True))
    assert ch.sent[0][2] is True


# --- EmailChannel (SMTP is faked, nothing touches the network) ---


class FakeSMTP:
    instances = []
    fail = False

    def __init__(self, host, port):
        self.logged_in = None
        self.messages = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        if FakeSMTP.fail:
            raise OSError("smtp down")
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, msg):
        self.messages.append(msg)


@pytest.fixture
def email(monkeypatch):
    FakeSMTP.instances, FakeSMTP.fail = [], False
    monkeypatch.setattr(notify.smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(retry_util.time, "sleep", lambda s: None)
    ch = EmailChannel()
    ch.email_from, ch.email_password, ch.email_to = "from@example.com", "app-pw", "to@example.com"
    return ch


def test_email_is_sent_with_login_and_subject_prefix(email):
    assert email.send("Start X", "body text") is True
    smtp = FakeSMTP.instances[0]
    assert smtp.logged_in == ("from@example.com", "app-pw")
    assert smtp.messages[0]["Subject"] == "[ffai] Start X"
    assert smtp.messages[0]["To"] == "to@example.com"


def test_email_failure_returns_false_and_does_not_raise(email):
    FakeSMTP.fail = True
    assert email.send("Start X", "body") is False
    assert len(FakeSMTP.instances) == 3  # three tries before giving up


def test_email_channel_needs_all_three_settings(email):
    assert email.is_configured() is True
    email.email_to = ""
    assert email.is_configured() is False
