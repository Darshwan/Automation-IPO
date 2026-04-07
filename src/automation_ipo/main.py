from __future__ import annotations

import argparse
import time

from .config import Settings, get_settings
from .ipo_service import IPOAutomationService
from .meroshare_client import MockMeroShareClient
from .models import ApplicationPreferences
from .notifier import ConsoleNotifier, EmailNotifier, Notifier
from .state_store import SeenIPOStore


def build_notifier(settings: Settings) -> Notifier:
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
        )

    return ConsoleNotifier()


def build_service(settings: Settings | None = None) -> IPOAutomationService:
    settings = settings or get_settings()

    client = MockMeroShareClient()
    notifier = build_notifier(settings)
    seen_store = SeenIPOStore(settings.ipo_state_file)

    preferences = ApplicationPreferences(
        share_quantity=10,
        apply_enabled=False,
    )

    return IPOAutomationService(
        client=client,
        notifier=notifier,
        seen_store=seen_store,
        preferences=preferences,
    )


def run(once: bool) -> None:
    settings = get_settings()
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(once=args.once)


if __name__ == "__main__":
    main()
