"""Spot gold (XAU/USD) market closures.

Convention implemented (standard retail spot-gold schedule, expressed in New York
local time so US daylight saving is handled by the tz database):
  - daily maintenance break 17:00-18:00 America/New_York, Monday-Thursday
  - weekly close Friday 17:00 NY, weekly open Sunday 18:00 NY
  - full-day closures listed in config/closures.json ("closed")
VERIFICATION STATUS: see docs/research/market-hours.md. Until that report confirms
the schedule, treat the break length as approximate. The functions here are used
to classify data gaps; they never create data.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

from .timeutil import NY, to_utc

_closed_dates: set[date] = set()
_thin_dates: set[date] = set()
_loaded_from: Path | None = None

DAILY_BREAK_START = time(17, 0)
DAILY_BREAK_END = time(18, 0)


def load_closures(path: str | Path) -> None:
    global _closed_dates, _thin_dates, _loaded_from
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    _closed_dates = {date.fromisoformat(d) for d in data.get("closed", [])}
    _thin_dates = {date.fromisoformat(d) for d in data.get("thin", [])}
    _loaded_from = p


def closed_dates() -> set[date]:
    return set(_closed_dates)


def is_closed(ts: datetime) -> bool:
    """True when spot gold is not trading at instant ts."""
    utc = to_utc(ts)
    if utc.date() in _closed_dates:      # full-day closures are listed as UTC calendar dates
        return True
    ny = utc.astimezone(NY)
    wd = ny.weekday()  # Mon=0 ... Sun=6
    t = ny.time()
    if wd == 5:  # Saturday
        return True
    if wd == 4 and t >= DAILY_BREAK_START:  # Friday after 17:00
        return True
    if wd == 6 and t < DAILY_BREAK_END:  # Sunday before 18:00
        return True
    if wd in (0, 1, 2, 3) and DAILY_BREAK_START <= t < DAILY_BREAK_END:
        return True
    return False


def closed_for_span(start: datetime, end: datetime, probe_seconds: int = 60) -> bool:
    """True if the market is closed for the whole [start, end) span (probed every minute)."""
    start, end = to_utc(start), to_utc(end)
    if end <= start:
        return True
    t = start
    while t < end:
        if not is_closed(t):
            return False
        t += timedelta(seconds=probe_seconds)
    return True


def is_thin(d: date) -> bool:
    return d in _thin_dates
