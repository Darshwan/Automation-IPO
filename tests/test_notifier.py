from __future__ import annotations

from datetime import datetime, timezone

import pytest

from automation_ipo.config import Settings
from automation_ipo.main import build_notifier
from automation_ipo.models import IPORecord
from automation_ipo.notifier import EmailNotifier


class FakeSMTP:
    instances: list["FakeSMTP"] = []

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.started_tls = False
        self.logged_in: tuple[str, str] | None = None
        self.sent_messages = []
        FakeSMTP.instances.append(self)

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = (exc_type, exc, tb)

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.logged_in = (username, password)

    def send_message(self, message) -> None:
        self.sent_messages.append(message)


def make_ipo() -> IPORecord:
    now = datetime.now(timezone.utc)
    return IPORecord(
        symbol="XYZ",
        company_name="XYZ Hydropower Ltd.",
        open_at=now,
        close_at=None,
        source_id="source-xyz",
    )


def test_email_notifier_sends_message(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSMTP.instances.clear()
    monkeypatch.setattr("automation_ipo.notifier.smtplib.SMTP", FakeSMTP)

    notifier = EmailNotifier(
        smtp_host="smtp.example.com",
        smtp_port=2525,
        smtp_username="user@example.com",
        smtp_password="secret",
        smtp_use_tls=True,
        from_email="bot@example.com",
        to_email="user@example.com",
    )

    notifier.on_new_ipo(make_ipo())

    assert len(FakeSMTP.instances) == 1
    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.example.com"
    assert smtp.port == 2525
    assert smtp.started_tls is True
    assert smtp.logged_in == ("user@example.com", "secret")
    assert len(smtp.sent_messages) == 1
    message = smtp.sent_messages[0]
    assert message["Subject"] == "New IPO detected: XYZ"
    assert message["From"] == "bot@example.com"
    assert message["To"] == "user@example.com"


def test_build_notifier_rejects_missing_email_settings() -> None:
    settings = Settings(notifier="email", notify_email="user@example.com")

    with pytest.raises(ValueError, match="Email notifier requires"):
        build_notifier(settings)