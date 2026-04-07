from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from automation_ipo.main import build_client
from automation_ipo.config import Settings
from automation_ipo.main import LIVE_APPLY_CONFIRMATION_TEXT
from automation_ipo.meroshare_client import BrowserMeroShareClient, HttpMeroShareClient


def test_http_client_fetches_ipos_from_json_payload() -> None:
    requests: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        payload = body.decode() if body else None
        requests.append((request.method, str(request.url), request.headers.get("content-type") and {"content-type": request.headers.get("content-type")}))
        if request.url.path == "/login":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/ipos":
            return httpx.Response(
                200,
                json=[
                    {
                        "symbol": "ABC",
                        "company_name": "ABC Energy Ltd.",
                        "open_at": "2026-04-07T10:00:00Z",
                        "close_at": None,
                        "source_id": "abc-1",
                    }
                ],
            )
        raise AssertionError(f"Unexpected path: {request.url.path}")

    transport = httpx.MockTransport(handler)
    client = HttpMeroShareClient(
        base_url="https://example.test",
        login_url="/login",
        open_ipos_url="/ipos",
        apply_url="/apply",
        username="user",
        password="pass",
        totp_secret=None,
        client=httpx.Client(base_url="https://example.test", transport=transport),
    )

    ipos = client.fetch_open_ipos()

    assert len(ipos) == 1
    ipo = ipos[0]
    assert ipo.symbol == "ABC"
    assert ipo.company_name == "ABC Energy Ltd."
    assert ipo.source_id == "abc-1"
    assert ipo.open_at == datetime(2026, 4, 7, 10, 0, tzinfo=timezone.utc)


def test_http_client_applies_ipo_with_post_body() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = HttpMeroShareClient(
        base_url="https://example.test",
        login_url=None,
        open_ipos_url="/ipos",
        apply_url="/apply",
        username=None,
        password=None,
        totp_secret=None,
        client=httpx.Client(base_url="https://example.test", transport=transport),
    )

    ipo = client._record_from_payload(
        {
            "symbol": "XYZ",
            "company_name": "XYZ Hydropower Ltd.",
            "open_at": "2026-04-07T10:00:00Z",
            "source_id": "xyz-1",
        }
    )

    assert client.apply_for_ipo(ipo, 20) is True
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/apply"


def test_build_client_rejects_http_mode_without_open_url() -> None:
    settings = Settings(meroshare_client="http")

    with pytest.raises(ValueError, match="meroshare_open_ipos_url"):
        build_client(settings)


def test_build_client_rejects_browser_mode_without_required_settings() -> None:
    settings = Settings(meroshare_client="browser")

    with pytest.raises(ValueError, match="Missing required browser MeroShare settings"):
        build_client(settings)


def test_build_client_creates_browser_client_with_minimum_required_settings() -> None:
    settings = Settings(
        meroshare_client="browser",
        meroshare_depository_participant="NMB Capital",
        meroshare_username="demo-user",
        meroshare_password="demo-pass",
        meroshare_totp_secret="ABCDEFGHIJKLMNOP",
        meroshare_apply_dry_run=True,
    )

    client = build_client(settings)

    assert isinstance(client, BrowserMeroShareClient)


def test_build_client_browser_uses_dry_run_default() -> None:
    settings = Settings(
        meroshare_client="browser",
        meroshare_depository_participant="NMB Capital",
        meroshare_username="demo-user",
        meroshare_password="demo-pass",
        meroshare_totp_secret="ABCDEFGHIJKLMNOP",
    )

    client = build_client(settings)

    assert isinstance(client, BrowserMeroShareClient)


def test_build_client_blocks_live_apply_without_confirmation_phrase() -> None:
    settings = Settings(
        meroshare_client="browser",
        meroshare_depository_participant="NMB Capital",
        meroshare_username="demo-user",
        meroshare_password="demo-pass",
        meroshare_totp_secret="ABCDEFGHIJKLMNOP",
        apply_enabled=True,
        meroshare_apply_dry_run=False,
        meroshare_legal_acknowledged=True,
        meroshare_crn_number="1234567890123456",
        meroshare_transaction_pin="1234",
    )

    with pytest.raises(ValueError, match="meroshare_live_apply_confirmation"):
        build_client(settings)


def test_build_client_blocks_live_apply_without_legal_acknowledgement() -> None:
    settings = Settings(
        meroshare_client="browser",
        meroshare_depository_participant="NMB Capital",
        meroshare_username="demo-user",
        meroshare_password="demo-pass",
        meroshare_totp_secret="ABCDEFGHIJKLMNOP",
        apply_enabled=True,
        meroshare_apply_dry_run=False,
        meroshare_live_apply_confirmation=LIVE_APPLY_CONFIRMATION_TEXT,
        meroshare_legal_acknowledged=False,
        meroshare_crn_number="1234567890123456",
        meroshare_transaction_pin="1234",
    )

    with pytest.raises(ValueError, match="meroshare_legal_acknowledged"):
        build_client(settings)


def test_build_client_allows_live_apply_with_confirmation_phrase() -> None:
    settings = Settings(
        meroshare_client="browser",
        meroshare_depository_participant="NMB Capital",
        meroshare_username="demo-user",
        meroshare_password="demo-pass",
        meroshare_totp_secret="ABCDEFGHIJKLMNOP",
        apply_enabled=True,
        meroshare_apply_dry_run=False,
        meroshare_live_apply_confirmation=LIVE_APPLY_CONFIRMATION_TEXT,
        meroshare_legal_acknowledged=True,
        meroshare_crn_number="1234567890123456",
        meroshare_transaction_pin="1234",
    )

    client = build_client(settings)

    assert isinstance(client, BrowserMeroShareClient)


def test_browser_row_parser_extracts_symbol_and_dates() -> None:
    client = BrowserMeroShareClient(
        base_url="https://example.test",
        depository_participant="NMB Capital",
        username="demo-user",
        password="demo-pass",
        totp_secret="ABCDEFGHIJKLMNOP",
        crn_number=None,
        transaction_pin=None,
    )
    now = datetime(2026, 4, 7, 0, 0, tzinfo=timezone.utc)

    symbol, company_name, open_at, close_at = client._parse_asba_row_fields(
        "Mega Hydropower Ltd. (MEGA)\nOpen: 2026-04-10\nClose: 2026-04-14",
        ["Mega Hydropower Ltd. (MEGA)", "2026-04-10", "2026-04-14"],
        index=0,
        fallback_open_at=now,
    )

    assert symbol == "MEGA"
    assert company_name == "Mega Hydropower Ltd."
    assert open_at == datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
    assert close_at == datetime(2026, 4, 14, 0, 0, tzinfo=timezone.utc)