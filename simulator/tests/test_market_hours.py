import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market_hours import MarketHoursConfig, is_market_open


def test_market_hours_gate_accepts_regular_session():
    cfg = MarketHoursConfig(
        enabled=True,
        timezone="America/New_York",
        open_time="09:30",
        close_time="16:00",
    )
    now = datetime(2026, 7, 20, 10, 0, tzinfo=ZoneInfo("America/New_York"))

    assert is_market_open(cfg, now=now)


def test_market_hours_gate_blocks_weekends_and_after_hours():
    cfg = MarketHoursConfig(enabled=True)

    saturday = datetime(2026, 7, 18, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    evening = datetime(2026, 7, 20, 20, 0, tzinfo=ZoneInfo("America/New_York"))

    assert not is_market_open(cfg, now=saturday)
    assert not is_market_open(cfg, now=evening)


def test_market_hours_gate_can_be_disabled():
    cfg = MarketHoursConfig(enabled=False)
    saturday = datetime(2026, 7, 18, 10, 0, tzinfo=ZoneInfo("America/New_York"))

    assert is_market_open(cfg, now=saturday)
