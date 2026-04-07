from __future__ import annotations

from dataclasses import dataclass

from .meroshare_client import MeroShareClient
from .models import ApplicationPreferences, IPORecord
from .notifier import Notifier
from .state_store import SeenIPOStore


@dataclass
class SyncResult:
    fetched_count: int
    new_count: int
    applied_count: int


class IPOAutomationService:
    def __init__(
        self,
        client: MeroShareClient,
        notifier: Notifier,
        seen_store: SeenIPOStore,
        preferences: ApplicationPreferences,
    ):
        self._client = client
        self._notifier = notifier
        self._seen_store = seen_store
        self._preferences = preferences

    def sync_once(self) -> SyncResult:
        seen_ids = self._seen_store.load()
        fetched = self._client.fetch_open_ipos()

        new_ipos: list[IPORecord] = [ipo for ipo in fetched if ipo.source_id not in seen_ids]
        applied_count = 0

        for ipo in new_ipos:
            self._notifier.on_new_ipo(ipo)
            seen_ids.add(ipo.source_id)

            if self._preferences.apply_enabled:
                success = self._client.apply_for_ipo(ipo, self._preferences.share_quantity)
                self._notifier.on_application_result(ipo, success, self._preferences.share_quantity)
                if success:
                    applied_count += 1

        self._seen_store.save(seen_ids)
        return SyncResult(fetched_count=len(fetched), new_count=len(new_ipos), applied_count=applied_count)
