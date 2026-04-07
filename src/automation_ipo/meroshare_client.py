from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import hashlib
from typing import Any
from contextlib import contextmanager

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


class BrowserMeroShareClient(MeroShareClient):
    """Browser-based client for real MeroShare UI workflows with dry-run safety by default."""

    def __init__(
        self,
        base_url: str,
        depository_participant: str,
        username: str,
        password: str,
        totp_secret: str,
        crn_number: str | None,
        transaction_pin: str | None,
        apply_dry_run: bool = True,
        headless: bool = True,
        timeout_ms: int = 30000,
        playwright_factory=None,
    ):
        self._base_url = base_url.rstrip("/")
        self._depository_participant = depository_participant
        self._username = username
        self._password = password
        self._totp_secret = totp_secret
        self._crn_number = crn_number
        self._transaction_pin = transaction_pin
        self._apply_dry_run = apply_dry_run
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._playwright_factory = playwright_factory

    def fetch_open_ipos(self) -> list[IPORecord]:
        with self._open_page() as page:
            self._login(page)
            self._goto_asba(page)
            return self._extract_asba_ipos(page)

    def apply_for_ipo(self, ipo: IPORecord, share_quantity: int) -> bool:
        with self._open_page() as page:
            self._login(page)
            self._goto_asba(page)
            self._open_issue_form(page, ipo)
            self._fill_issue_form(page, share_quantity)

            if self._apply_dry_run:
                return False

            self._click_first(
                page,
                [
                    "button:has-text('Apply')",
                    "button:has-text('Submit')",
                    "button[type='submit']",
                ],
                "Could not find final apply button",
            )
            return True

    @contextmanager
    def _open_page(self):
        factory = self._playwright_factory
        if factory is None:
            try:
                from playwright.sync_api import sync_playwright
            except ImportError as exc:  # pragma: no cover - dependency issue handled at runtime
                raise ValueError(
                    "playwright is required for meroshare_client=browser. Install with: pip install playwright"
                ) from exc
            factory = sync_playwright

        with factory() as playwright:
            browser = playwright.chromium.launch(headless=self._headless)
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(self._timeout_ms)
            try:
                yield page
            finally:
                context.close()
                browser.close()

    def _login(self, page) -> None:
        page.goto(f"{self._base_url}/#/login", wait_until="domcontentloaded")

        self._fill_participant(page)
        self._fill_first(
            page,
            ["input[formcontrolname='username']", "input[name='username']", "input[type='text']"],
            self._username,
            "Could not find username input",
        )
        self._fill_first(
            page,
            ["input[formcontrolname='password']", "input[name='password']", "input[type='password']"],
            self._password,
            "Could not find password input",
        )

        otp_code = self._build_totp_code()
        self._fill_first(
            page,
            ["input[formcontrolname='otp']", "input[name='otp']", "input[placeholder*='OTP']"],
            otp_code,
            "Could not find OTP input",
        )

        self._click_first(
            page,
            ["button[type='submit']", "button:has-text('Login')", "button:has-text('Sign In')"],
            "Could not find login button",
        )

        page.wait_for_timeout(1000)

    def _goto_asba(self, page) -> None:
        page.goto(f"{self._base_url}/#/asba", wait_until="domcontentloaded")
        page.wait_for_timeout(1000)

    def _extract_asba_ipos(self, page) -> list[IPORecord]:
        self._click_if_visible(page, ["text=Apply for issue", "text=Apply For Issue"])

        rows = page.locator("table tbody tr")
        count = rows.count()
        now = datetime.now(timezone.utc)
        results: list[IPORecord] = []

        for index in range(count):
            text = rows.nth(index).inner_text().strip()
            if not text:
                continue

            symbol = self._extract_symbol(text, index)
            company_name = self._extract_company_name(text, index)
            source_id = self._build_source_id(text, index)

            results.append(
                IPORecord(
                    symbol=symbol,
                    company_name=company_name,
                    open_at=now,
                    close_at=None,
                    source_id=source_id,
                )
            )

        return results

    def _open_issue_form(self, page, ipo: IPORecord) -> None:
        row = page.locator(f"table tbody tr:has-text('{ipo.symbol}')")
        if row.count() == 0:
            row = page.locator(f"table tbody tr:has-text('{ipo.company_name}')")
        if row.count() == 0:
            raise ValueError(f"Could not find ASBA row for IPO {ipo.symbol}")

        target_row = row.first
        target_row.click()
        self._click_if_visible(
            page,
            [
                "button:has-text('Apply')",
                "button:has-text('Proceed')",
            ],
        )

    def _fill_issue_form(self, page, share_quantity: int) -> None:
        self._fill_first(
            page,
            [
                "input[formcontrolname='appliedKitta']",
                "input[name='quantity']",
                "input[placeholder*='Quantity']",
                "input[type='number']",
            ],
            str(share_quantity),
            "Could not find quantity input in apply form",
        )

        if self._crn_number:
            self._fill_first(
                page,
                [
                    "input[formcontrolname='crnNumber']",
                    "input[name='crn']",
                    "input[placeholder*='CRN']",
                ],
                self._crn_number,
                "Could not find CRN input in apply form",
            )

        if self._transaction_pin:
            self._fill_first(
                page,
                [
                    "input[formcontrolname='transactionPIN']",
                    "input[name='transactionPIN']",
                    "input[placeholder*='PIN']",
                    "input[type='password']",
                ],
                self._transaction_pin,
                "Could not find transaction PIN input in apply form",
            )

    def _fill_participant(self, page) -> None:
        selectors = [
            "select[formcontrolname='depositoryParticipant']",
            "select[name='depositoryParticipant']",
            "select[formcontrolname='bank']",
            "select",
        ]
        for selector in selectors:
            locator = page.locator(selector).first
            if locator.count() == 0:
                continue
            try:
                locator.select_option(label=self._depository_participant)
                return
            except Exception:
                try:
                    locator.select_option(value=self._depository_participant)
                    return
                except Exception:
                    continue
        raise ValueError("Could not find Depository Participant selector")

    def _build_totp_code(self) -> str:
        if pyotp is None:
            raise ValueError("pyotp is required when using browser MeroShare login")
        return pyotp.TOTP(self._totp_secret).now()

    def _fill_first(self, page, selectors: list[str], value: str, error_message: str) -> None:
        for selector in selectors:
            locator = page.locator(selector).first
            if locator.count() == 0:
                continue
            locator.fill(value)
            return
        raise ValueError(error_message)

    def _click_first(self, page, selectors: list[str], error_message: str) -> None:
        for selector in selectors:
            locator = page.locator(selector).first
            if locator.count() == 0:
                continue
            locator.click()
            return
        raise ValueError(error_message)

    def _click_if_visible(self, page, selectors: list[str]) -> None:
        for selector in selectors:
            locator = page.locator(selector).first
            if locator.count() > 0:
                locator.click()
                return

    def _extract_symbol(self, row_text: str, index: int) -> str:
        tokens = [token.strip("()") for token in row_text.replace("\n", " ").split()]
        for token in tokens:
            if token.isupper() and 2 <= len(token) <= 10 and token.isalpha():
                return token
        return f"IPO{index + 1}"

    def _extract_company_name(self, row_text: str, index: int) -> str:
        first_line = row_text.splitlines()[0].strip() if row_text.splitlines() else ""
        if first_line:
            return first_line[:120]
        return f"Issue {index + 1}"

    def _build_source_id(self, row_text: str, index: int) -> str:
        digest = hashlib.sha1(row_text.encode("utf-8")).hexdigest()[:16]
        return f"asba-{index + 1}-{digest}"
