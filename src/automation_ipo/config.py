from __future__ import annotations

from typing import Literal
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ipo_state_file: Path = Path(".data/seen_ipos.json")
    check_interval_seconds: int = 60

    notifier: Literal["console", "email"] = "console"
    notify_email: str | None = None
    notify_phone: str | None = None

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    smtp_from_email: str | None = None

    apply_enabled: bool = False
    apply_share_quantity: int = 10
    meroshare_apply_dry_run: bool = True
    meroshare_live_apply_confirmation: str | None = None

    meroshare_depository_participant: str | None = None
    meroshare_crn_number: str | None = None
    meroshare_transaction_pin: str | None = None
    meroshare_browser_headless: bool = True

    meroshare_client: Literal["mock", "http", "browser"] = "mock"
    meroshare_login_url: str | None = None
    meroshare_open_ipos_url: str | None = None
    meroshare_apply_url: str | None = None
    meroshare_timeout_seconds: float = 30.0

    meroshare_username: str | None = None
    meroshare_password: str | None = None
    meroshare_totp_secret: str | None = None
    meroshare_base_url: str = "https://meroshare.cdsc.com.np"

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None


def get_settings() -> Settings:
    return Settings()
