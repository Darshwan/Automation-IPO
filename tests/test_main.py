from __future__ import annotations

from automation_ipo.config import Settings
from automation_ipo.main import build_notifier, build_service
from automation_ipo.models import IPORecord
from datetime import datetime, timezone


def test_build_service_uses_apply_preferences_from_settings() -> None:
    settings = Settings(apply_enabled=True, apply_share_quantity=40)

    service = build_service(settings)

    assert service._preferences.apply_enabled is True
    assert service._preferences.share_quantity == 40


def test_build_notifier_redacts_secrets_from_console_output(capsys) -> None:
    settings = Settings(
        notifier="console",
        meroshare_password="MYSECRET1234",
    )
    notifier = build_notifier(settings)
    ipo = IPORecord(
        symbol="MYSECRET1234",
        company_name="ACME MYSECRET1234",
        open_at=datetime.now(timezone.utc),
        close_at=None,
        source_id="source-1",
    )

    notifier.on_new_ipo(ipo)

    output = capsys.readouterr().out
    assert "MYSECRET1234" not in output
    assert "[REDACTED]" in output
