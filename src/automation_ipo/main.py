from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import time

from .config import Settings, get_settings
from .ipo_service import IPOAutomationService
from .meroshare_client import BrowserMeroShareClient, HttpMeroShareClient, MockMeroShareClient, MeroShareClient
from .models import ApplicationPreferences
from .notifier import ConsoleNotifier, EmailNotifier, Notifier
from .state_store import SeenIPOStore


LIVE_APPLY_CONFIRMATION_TEXT = "I_UNDERSTAND_AND_CONFIRM_LIVE_IPO_APPLY"
LEGAL_ACKNOWLEDGEMENT_TEXT = "I_HAVE_REVIEWED_TOS_AND_ACCEPT_RISK"


def _secret_values_from_settings(settings: Settings) -> list[str]:
    values = [
        settings.meroshare_password,
        settings.meroshare_totp_secret,
        settings.meroshare_crn_number,
        settings.meroshare_transaction_pin,
        settings.smtp_password,
        settings.twilio_auth_token,
    ]
    return [value for value in values if value]


def build_notifier(settings: Settings) -> Notifier:
    secrets = _secret_values_from_settings(settings)

    if settings.notifier == "email":
        if not settings.smtp_host or not settings.smtp_from_email or not settings.notify_email:
            raise ValueError(
                "Email notifier requires smtp_host, smtp_from_email, and notify_email settings"
            )
        return EmailNotifier(
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_username=settings.smtp_username,
            smtp_password=settings.smtp_password,
            smtp_use_tls=settings.smtp_use_tls,
            from_email=settings.smtp_from_email,
            to_email=settings.notify_email,
            secrets_to_redact=secrets,
        )

    return ConsoleNotifier(secrets_to_redact=secrets)


def build_client(settings: Settings, transport=None, playwright_factory=None) -> MeroShareClient:
    if settings.meroshare_client == "mock":
        return MockMeroShareClient()

    if settings.meroshare_client == "browser":
        required = {
            "meroshare_depository_participant": settings.meroshare_depository_participant,
            "meroshare_username": settings.meroshare_username,
            "meroshare_password": settings.meroshare_password,
            "meroshare_totp_secret": settings.meroshare_totp_secret,
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing required browser MeroShare settings: {', '.join(missing)}")

        live_apply_confirmed = False
        if settings.apply_enabled and not settings.meroshare_apply_dry_run:
            if not settings.meroshare_legal_acknowledged:
                raise ValueError(
                    "Live apply is blocked until meroshare_legal_acknowledged=true is explicitly set"
                )
            if settings.meroshare_live_apply_confirmation != LIVE_APPLY_CONFIRMATION_TEXT:
                raise ValueError(
                    "Live apply requires exact meroshare_live_apply_confirmation value"
                )
            if not settings.meroshare_crn_number or not settings.meroshare_transaction_pin:
                raise ValueError("Live apply requires meroshare_crn_number and meroshare_transaction_pin")
            live_apply_confirmed = True

        return BrowserMeroShareClient(
            base_url=settings.meroshare_base_url,
            depository_participant=settings.meroshare_depository_participant,
            username=settings.meroshare_username,
            password=settings.meroshare_password,
            totp_secret=settings.meroshare_totp_secret,
            crn_number=settings.meroshare_crn_number,
            transaction_pin=settings.meroshare_transaction_pin,
            apply_dry_run=settings.meroshare_apply_dry_run,
            headless=settings.meroshare_browser_headless,
            timeout_ms=int(settings.meroshare_timeout_seconds * 1000),
            live_apply_confirmed=live_apply_confirmed,
            playwright_factory=playwright_factory,
        )

    if not settings.meroshare_open_ipos_url:
        raise ValueError("meroshare_open_ipos_url is required when meroshare_client=http")

    return HttpMeroShareClient(
        base_url=settings.meroshare_base_url,
        login_url=settings.meroshare_login_url,
        open_ipos_url=settings.meroshare_open_ipos_url,
        apply_url=settings.meroshare_apply_url,
        username=settings.meroshare_username,
        password=settings.meroshare_password,
        totp_secret=settings.meroshare_totp_secret,
        timeout_seconds=settings.meroshare_timeout_seconds,
        client=transport,
    )


def _validate_live_apply_legal_gate(settings: Settings) -> None:
    if settings.apply_enabled and not settings.meroshare_apply_dry_run:
        if not settings.meroshare_legal_acknowledged:
            raise ValueError(
                "Live apply is blocked until meroshare_legal_acknowledged=true is explicitly set"
            )


def _print_startup_warning_banner(settings: Settings) -> None:
    print("[LEGAL WARNING] This automation may violate third-party terms or local regulations.")
    print("[LEGAL WARNING] Use at your own risk and review official MeroShare/CDSC policies before live use.")
    if settings.apply_enabled and not settings.meroshare_apply_dry_run:
        print("[LIVE APPLY MODE] Live submission requested. Legal acknowledgement and confirmation gates are enforced.")
    else:
        print("[SAFE MODE] Dry-run or apply-disabled mode is active.")


def _build_portfolio_demo_settings(settings: Settings) -> Settings:
    data = settings.model_dump()
    data.update(
        {
            "meroshare_client": "mock",
            "apply_enabled": False,
            "meroshare_apply_dry_run": True,
            "ipo_state_file": Path(".data/portfolio_demo_seen.json"),
        }
    )
    return Settings.model_validate(data)


def run_portfolio_demo(settings: Settings, cycles: int = 2) -> Path:
    if cycles < 1:
        raise ValueError("demo cycles must be at least 1")

    demo_settings = _build_portfolio_demo_settings(settings)
    demo_state = demo_settings.ipo_state_file
    report_path = Path(".data/portfolio_demo_report.md")

    if demo_state.exists():
        demo_state.unlink()

    service = build_service(demo_settings)
    results = []
    for index in range(cycles):
        result = service.sync_once()
        results.append(result)
        print(
            f"[PORTFOLIO DEMO] cycle={index + 1} fetched={result.fetched_count} new={result.new_count} applied={result.applied_count}"
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Portfolio Demo Report",
        "",
        f"Generated at: {timestamp}",
        "",
        "## Demo Outcome",
        "",
        "This demo uses the mock provider with apply disabled to safely demonstrate dedup behavior.",
        "",
        "| Cycle | Fetched | New | Applied |",
        "|---|---:|---:|---:|",
    ]
    for index, result in enumerate(results, start=1):
        lines.append(
            f"| {index} | {result.fetched_count} | {result.new_count} | {result.applied_count} |"
        )
    lines.append("")
    lines.append(f"State file used: {demo_state.as_posix()}")
    lines.append("")
    lines.append("Expected signal: cycle 1 shows new=1, later cycles show new=0 because state persistence prevents duplicates.")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[PORTFOLIO DEMO] report written to {report_path.as_posix()}")
    return report_path


def build_service(settings: Settings | None = None) -> IPOAutomationService:
    settings = settings or get_settings()
    _validate_live_apply_legal_gate(settings)

    client = build_client(settings)
    notifier = build_notifier(settings)
    seen_store = SeenIPOStore(settings.ipo_state_file)

    preferences = ApplicationPreferences(
        share_quantity=settings.apply_share_quantity,
        apply_enabled=settings.apply_enabled,
    )

    return IPOAutomationService(
        client=client,
        notifier=notifier,
        seen_store=seen_store,
        preferences=preferences,
    )


def run(once: bool) -> None:
    settings = get_settings()
    _print_startup_warning_banner(settings)
    service = build_service(settings)

    while True:
        result = service.sync_once()
        print(
            f"[SYNC] fetched={result.fetched_count} new={result.new_count} applied={result.applied_count}"
        )
        if once:
            return
        time.sleep(settings.check_interval_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automation IPO runner")
    parser.add_argument("--once", action="store_true", help="Run one sync cycle and exit")
    parser.add_argument(
        "--portfolio-demo",
        action="store_true",
        help="Run a safe, deterministic mock demo and generate a portfolio report",
    )
    parser.add_argument(
        "--demo-cycles",
        type=int,
        default=2,
        help="Number of cycles for portfolio demo mode",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    if args.portfolio_demo:
        _print_startup_warning_banner(settings)
        run_portfolio_demo(settings=settings, cycles=args.demo_cycles)
        return
    run(once=args.once)


if __name__ == "__main__":
    main()
