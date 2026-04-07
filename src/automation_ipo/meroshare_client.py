from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

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
