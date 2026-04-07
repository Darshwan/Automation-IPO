from __future__ import annotations

from abc import ABC, abstractmethod
import smtplib
from email.message import EmailMessage
from typing import Iterable

from .models import IPORecord


def redact_text(value: str, secrets: Iterable[str | None]) -> str:
    redacted = value
    for secret in secrets:
        if secret and len(secret) >= 4:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


class Notifier(ABC):
    @abstractmethod
    def on_new_ipo(self, ipo: IPORecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def on_application_result(self, ipo: IPORecord, success: bool, share_quantity: int) -> None:
        raise NotImplementedError


class ConsoleNotifier(Notifier):
    def __init__(self, secrets_to_redact: list[str] | None = None):
        self._secrets_to_redact = secrets_to_redact or []

    def on_new_ipo(self, ipo: IPORecord) -> None:
        message = (
            f"[NEW IPO] {ipo.company_name} ({ipo.symbol}) | opens: {ipo.open_at.isoformat()} | source_id: {ipo.source_id}"
        )
        print(redact_text(message, self._secrets_to_redact))

    def on_application_result(self, ipo: IPORecord, success: bool, share_quantity: int) -> None:
        status = "SUCCESS" if success else "FAILED"
        message = (
            f"[APPLICATION {status}] {ipo.company_name} ({ipo.symbol}) | shares: {share_quantity} | source_id: {ipo.source_id}"
        )
        print(redact_text(message, self._secrets_to_redact))


class EmailNotifier(Notifier):
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str | None,
        smtp_password: str | None,
        smtp_use_tls: bool,
        from_email: str,
        to_email: str,
        secrets_to_redact: list[str] | None = None,
    ):
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_username = smtp_username
        self._smtp_password = smtp_password
        self._smtp_use_tls = smtp_use_tls
        self._from_email = from_email
        self._to_email = to_email
        self._secrets_to_redact = secrets_to_redact or []

    def on_new_ipo(self, ipo: IPORecord) -> None:
        subject = f"New IPO detected: {ipo.symbol}"
        body = (
            f"A new IPO was detected.\n\n"
            f"Company: {ipo.company_name}\n"
            f"Symbol: {ipo.symbol}\n"
            f"Opens at: {ipo.open_at.isoformat()}\n"
            f"Source ID: {ipo.source_id}\n"
        )
        self._send_message(subject=subject, body=body)

    def on_application_result(self, ipo: IPORecord, success: bool, share_quantity: int) -> None:
        status = "successful" if success else "failed"
        subject = f"IPO application {status}: {ipo.symbol}"
        body = (
            f"The IPO application finished with status: {status}.\n\n"
            f"Company: {ipo.company_name}\n"
            f"Symbol: {ipo.symbol}\n"
            f"Shares: {share_quantity}\n"
            f"Source ID: {ipo.source_id}\n"
        )
        self._send_message(subject=subject, body=body)

    def _send_message(self, subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = redact_text(subject, self._secrets_to_redact)
        message["From"] = self._from_email
        message["To"] = self._to_email
        message.set_content(redact_text(body, self._secrets_to_redact))

        with smtplib.SMTP(self._smtp_host, self._smtp_port) as smtp:
            if self._smtp_use_tls:
                smtp.starttls()
            if self._smtp_username and self._smtp_password:
                smtp.login(self._smtp_username, self._smtp_password)
            smtp.send_message(message)
