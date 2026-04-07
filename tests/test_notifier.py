from __future__ import annotations

from datetime import datetime, timezone

import pytest

from automation_ipo.config import Settings
from automation_ipo.main import build_notifier
from automation_ipo.models import IPORecord
from automation_ipo.notifier import ConsoleNotifier, EmailNotifier, redact_text


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


def make_secret_ipo(secret: str) -> IPORecord:
    now = datetime.now(timezone.utc)
    return IPORecord(
        symbol=secret,
        company_name=f"Company {secret}",
        open_at=now,
        close_at=None,
        source_id=f"id-{secret}",
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


def test_console_notifier_redacts_secret_in_log_output(capsys: pytest.CaptureFixture[str]) -> None:
    secret = "TOPSECRET1234"
    notifier = ConsoleNotifier(secrets_to_redact=[secret])

    notifier.on_new_ipo(make_secret_ipo(secret))

    captured = capsys.readouterr()
    assert secret not in captured.out
    assert "[REDACTED]" in captured.out


def test_email_notifier_redacts_secret_in_message(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSMTP.instances.clear()
    monkeypatch.setattr("automation_ipo.notifier.smtplib.SMTP", FakeSMTP)
    secret = "PIN9876"

    notifier = EmailNotifier(
        smtp_host="smtp.example.com",
        smtp_port=2525,
        smtp_username="user@example.com",
        smtp_password="secret",
        smtp_use_tls=True,
        from_email="bot@example.com",
        to_email="user@example.com",
        secrets_to_redact=[secret],
    )

    notifier.on_application_result(make_secret_ipo(secret), success=True, share_quantity=10)

    message = FakeSMTP.instances[0].sent_messages[0]
    raw_payload = message.as_string()
    assert secret not in raw_payload
    assert "[REDACTED]" in raw_payload


def test_redact_text_masks_only_configured_secrets() -> None:
    text = "password=abc12345 token=xyz98765"
    result = redact_text(text, ["abc12345"])

    assert "abc12345" not in result
    assert "xyz98765" in result