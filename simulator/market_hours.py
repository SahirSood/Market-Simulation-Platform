from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class MarketHoursConfig:
    enabled: bool
    timezone: str = "America/New_York"
    open_time: str = "09:30"
    close_time: str = "16:00"


def _parse_hhmm(value: str, fallback: time) -> time:
    try:
        hour, minute = str(value).split(":", 1)
        return time(hour=int(hour), minute=int(minute))
    except Exception:
        return fallback


def is_market_open(config: MarketHoursConfig, now: datetime | None = None) -> bool:
    if not config.enabled:
        return True

    try:
        tz = ZoneInfo(config.timezone)
    except Exception:
        tz = ZoneInfo("America/New_York")

    local_now = (now or datetime.now(tz)).astimezone(tz)
    if local_now.weekday() >= 5:
        return False

    open_time = _parse_hhmm(config.open_time, time(9, 30))
    close_time = _parse_hhmm(config.close_time, time(16, 0))
    current = local_now.time()
    return open_time <= current <= close_time
