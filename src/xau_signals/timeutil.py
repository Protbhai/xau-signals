"""Time helpers. Internals are UTC-aware datetimes; the user sees IST."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
IST = ZoneInfo("Asia/Kolkata")
NY = ZoneInfo("America/New_York")

INTERVAL_SECONDS = {
    "1m": 60, "2m": 120, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "60m": 3600, "4h": 14400, "1d": 86400,
}


def now_utc() -> datetime:
    return datetime.now(UTC)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime not allowed; attach a timezone first")
    return dt.astimezone(UTC)


def to_ist(dt: datetime) -> datetime:
    return to_utc(dt).astimezone(IST)


def fmt_ist(dt: datetime, with_date: bool = True) -> str:
    d = to_ist(dt)
    return d.strftime("%d %b %H:%M IST") if with_date else d.strftime("%H:%M IST")


def from_epoch(seconds: int | float) -> datetime:
    return datetime.fromtimestamp(float(seconds), UTC)


def interval_seconds(interval: str) -> int:
    try:
        return INTERVAL_SECONDS[interval]
    except KeyError as e:
        raise ValueError(f"unknown interval {interval!r}") from e


def floor_to_interval(dt: datetime, interval: str) -> datetime:
    sec = interval_seconds(interval)
    dt = to_utc(dt)
    epoch = int(dt.timestamp())
    return from_epoch(epoch - epoch % sec)


def candle_close_time(open_time: datetime, interval: str) -> datetime:
    return to_utc(open_time) + timedelta(seconds=interval_seconds(interval))
