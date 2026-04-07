from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IPORecord(BaseModel):
    """Minimal IPO descriptor used by the detection pipeline."""

    symbol: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    open_at: datetime
    close_at: datetime | None = None
    source_id: str = Field(min_length=1)


class ApplicationPreferences(BaseModel):
    """User-level automation settings for apply flow."""

    share_quantity: int = Field(default=10, ge=10)
    apply_enabled: bool = False
