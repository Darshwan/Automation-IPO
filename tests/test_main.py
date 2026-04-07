from __future__ import annotations

from automation_ipo.config import Settings
from automation_ipo.main import build_service


def test_build_service_uses_apply_preferences_from_settings() -> None:
    settings = Settings(apply_enabled=True, apply_share_quantity=40)

    service = build_service(settings)

    assert service._preferences.apply_enabled is True
    assert service._preferences.share_quantity == 40
