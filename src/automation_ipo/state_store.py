from __future__ import annotations

import json
from pathlib import Path


class SeenIPOStore:
    """Simple JSON-backed set store for source IPO IDs."""

    def __init__(self, file_path: Path):
        self._file_path = file_path

    def load(self) -> set[str]:
        if not self._file_path.exists():
            return set()
        data = json.loads(self._file_path.read_text(encoding="utf-8"))
        return set(data.get("seen_ids", []))

    def save(self, seen_ids: set[str]) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"seen_ids": sorted(seen_ids)}
        self._file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
