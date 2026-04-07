from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from automation_ipo.ipo_service import IPOAutomationService
from automation_ipo.meroshare_client import MeroShareClient
from automation_ipo.models import ApplicationPreferences, IPORecord
from automation_ipo.notifier import Notifier
from automation_ipo.state_store import SeenIPOStore


class FakeClient(MeroShareClient):
    def __init__(self, ipos: list[IPORecord]):
        self.ipos = ipos
        self.apply_calls: list[tuple[str, int]] = []

    def fetch_open_ipos(self) -> list[IPORecord]:
        return self.ipos

    def apply_for_ipo(self, ipo: IPORecord, share_quantity: int) -> bool:
        self.apply_calls.append((ipo.source_id, share_quantity))
        return True


class FakeNotifier(Notifier):
    def __init__(self):
        self.new_symbols: list[str] = []
        self.app_results: list[tuple[str, bool, int]] = []

    def on_new_ipo(self, ipo: IPORecord) -> None:
        self.new_symbols.append(ipo.symbol)

    def on_application_result(self, ipo: IPORecord, success: bool, share_quantity: int) -> None:
        self.app_results.append((ipo.symbol, success, share_quantity))


def make_ipo(source_id: str, symbol: str = "DEMO") -> IPORecord:
    now = datetime.now(timezone.utc)
    return IPORecord(
        symbol=symbol,
        company_name=f"{symbol} Company",
        open_at=now,
        close_at=None,
        source_id=source_id,
    )


def test_detects_only_new_ipos(tmp_path: Path) -> None:
    store = SeenIPOStore(tmp_path / "seen.json")
    first = make_ipo("id-1", symbol="AAA")

    client = FakeClient([first])
    notifier = FakeNotifier()

    service = IPOAutomationService(
        client=client,
        notifier=notifier,
        seen_store=store,
        preferences=ApplicationPreferences(share_quantity=10, apply_enabled=False),
    )

    result1 = service.sync_once()
    result2 = service.sync_once()

    assert result1.new_count == 1
    assert result2.new_count == 0
    assert notifier.new_symbols == ["AAA"]


def test_applies_when_enabled(tmp_path: Path) -> None:
    store = SeenIPOStore(tmp_path / "seen.json")
    ipo = make_ipo("id-2", symbol="BBB")

    client = FakeClient([ipo])
    notifier = FakeNotifier()

    service = IPOAutomationService(
        client=client,
        notifier=notifier,
        seen_store=store,
        preferences=ApplicationPreferences(share_quantity=20, apply_enabled=True),
    )

    result = service.sync_once()

    assert result.applied_count == 1
    assert client.apply_calls == [("id-2", 20)]
    assert notifier.app_results == [("BBB", True, 20)]
