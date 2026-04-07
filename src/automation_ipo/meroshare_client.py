from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from datetime import datetime, timezone

import httpx

try:
    import pyotp
except ImportError:  # pragma: no cover - optional dependency for live login flows
    pyotp = None

from .models import IPORecord


class MeroShareClient(ABC):
    """Abstract provider for IPO data and apply actions."""

    @abstractmethod
    def fetch_open_ipos(self) -> list[IPORecord]:
        raise NotImplementedError

    @abstractmethod
    def apply_for_ipo(self, ipo: IPORecord, share_quantity: int) -> bool:
        raise NotImplementedError


class MockMeroShareClient(MeroShareClient):
    """Development provider to exercise pipeline logic without live trading actions."""

    def fetch_open_ipos(self) -> list[IPORecord]:
        now = datetime.now(timezone.utc)
        return [
            IPORecord(
                symbol="DEMO",
                company_name="Demo Hydropower Ltd.",
                open_at=now,
                close_at=None,
                source_id="demo-ipo-1",
            )
        ]

    def apply_for_ipo(self, ipo: IPORecord, share_quantity: int) -> bool:
        _ = (ipo, share_quantity)
        return True


class HttpMeroShareClient(MeroShareClient):
    """HTTP-based client for a configurable MeroShare integration endpoint."""

    def __init__(
        self,
        base_url: str,
        login_url: str | None,
        open_ipos_url: str,
        apply_url: str | None,
        username: str | None,
        password: str | None,
        totp_secret: str | None,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._login_url = login_url
        self._open_ipos_url = open_ipos_url
        self._apply_url = apply_url
        self._username = username
        self._password = password
        self._totp_secret = totp_secret
        self._client = client or httpx.Client(base_url=self._base_url, timeout=timeout_seconds)
        self._logged_in = login_url is None

    def fetch_open_ipos(self) -> list[IPORecord]:
        self._ensure_login()
        response = self._client.get(self._open_ipos_url)
        response.raise_for_status()
        payload = response.json()
        return self._extract_ipos(payload)

    def apply_for_ipo(self, ipo: IPORecord, share_quantity: int) -> bool:
        if not self._apply_url:
            raise ValueError("apply_url is required to submit IPO applications")

        self._ensure_login()
        response = self._client.post(
            self._apply_url,
            json={
                "source_id": ipo.source_id,
                "symbol": ipo.symbol,
                "share_quantity": share_quantity,
            },
        )
        response.raise_for_status()
        return True

    def _ensure_login(self) -> None:
        if self._logged_in:
            return
        if not self._login_url:
            self._logged_in = True
            return
        if not self._username or not self._password:
            raise ValueError("username and password are required for live MeroShare login")

        payload: dict[str, Any] = {
            "username": self._username,
            "password": self._password,
        }
        if self._totp_secret:
            if pyotp is None:
                raise ValueError("pyotp is required when meroshare_totp_secret is configured")
            payload["totp"] = pyotp.TOTP(self._totp_secret).now()

        response = self._client.post(self._login_url, json=payload)
        response.raise_for_status()
        self._logged_in = True

    def _extract_ipos(self, payload: Any) -> list[IPORecord]:
        if isinstance(payload, list):
            raw_records = payload
        elif isinstance(payload, dict):
            for key in ("results", "data", "items", "ipos"):
                value = payload.get(key)
                if isinstance(value, list):
                    raw_records = value
                    break
            else:
                raw_records = [payload]
        else:
            raise ValueError("Unexpected IPO payload format")

        return [self._record_from_payload(item) for item in raw_records]

    def _record_from_payload(self, payload: Any) -> IPORecord:
        if not isinstance(payload, dict):
            raise ValueError("IPO payload entries must be objects")

        symbol = self._pick(payload, "symbol", "scrip", "stock_symbol")
        company_name = self._pick(payload, "company_name", "companyName", "name")
        source_id = self._pick(payload, "source_id", "sourceId", "id", "uuid")
        open_at = self._parse_datetime(self._pick(payload, "open_at", "openAt", "opening_time", "startDate"))
        close_at_raw = self._pick_optional(payload, "close_at", "closeAt", "closing_time", "endDate")
        close_at = self._parse_datetime(close_at_raw) if close_at_raw is not None else None

        return IPORecord(
            symbol=symbol,
            company_name=company_name,
            open_at=open_at,
            close_at=close_at,
            source_id=source_id,
        )

    def _pick(self, payload: dict[str, Any], *keys: str) -> str:
        value = self._pick_optional(payload, *keys)
        if value is None:
            joined = ", ".join(keys)
            raise ValueError(f"Missing required IPO field: {joined}")
        return str(value)

    def _pick_optional(self, payload: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in payload and payload[key] not in (None, ""):
                return payload[key]
        return None

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if not isinstance(value, str):
            raise ValueError("Datetime values must be strings or datetimes")
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
