from __future__ import annotations

from pathlib import Path
import pytest

from automation_ipo.config import Settings
from automation_ipo.main import (
    _print_startup_warning_banner,
    build_notifier,
    build_service,
    run_portfolio_demo,
)
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


def test_build_service_blocks_live_apply_without_legal_acknowledgement() -> None:
    settings = Settings(
        meroshare_client="browser",
        meroshare_depository_participant="NMB Capital",
        meroshare_username="demo-user",
        meroshare_password="demo-pass",
        meroshare_totp_secret="ABCDEFGHIJKLMNOP",
        apply_enabled=True,
        meroshare_apply_dry_run=False,
        meroshare_live_apply_confirmation="I_UNDERSTAND_AND_CONFIRM_LIVE_IPO_APPLY",
        meroshare_crn_number="1234567890123456",
        meroshare_transaction_pin="1234",
        meroshare_legal_acknowledged=False,
    )

    with pytest.raises(ValueError, match="meroshare_legal_acknowledged"):
        build_service(settings)


def test_startup_warning_banner_mentions_safe_mode(capsys) -> None:
    settings = Settings(apply_enabled=False)

    _print_startup_warning_banner(settings)

    output = capsys.readouterr().out
    assert "[LEGAL WARNING]" in output
    assert "[SAFE MODE]" in output


def test_portfolio_demo_generates_report_and_dedup_signal(capsys, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings()

    report_path = run_portfolio_demo(settings=settings, cycles=2)

    output = capsys.readouterr().out
    assert "[PORTFOLIO DEMO] cycle=1" in output
    assert "[PORTFOLIO DEMO] cycle=2" in output
    assert report_path.exists()

    report = report_path.read_text(encoding="utf-8")
    assert "| 1 | 1 | 1 | 0 |" in report
    assert "| 2 | 1 | 0 | 0 |" in report


def test_portfolio_demo_rejects_invalid_cycles() -> None:
    with pytest.raises(ValueError, match="demo cycles"):
        run_portfolio_demo(settings=Settings(), cycles=0)
