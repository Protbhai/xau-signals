"""The trading session: 09:00 (inclusive) to 15:00 (exclusive) Asia/Kolkata."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from . import market_hours
from .timeutil import IST, to_utc


@dataclass(frozen=True)
class SessionSpec:
    start: time = time(9, 0)
    end: time = time(15, 0)

    @staticmethod
    def from_strings(start: str, end: str) -> "SessionSpec":
        h1, m1 = map(int, start.split(":"))
        h2, m2 = map(int, end.split(":"))
        return SessionSpec(time(h1, m1), time(h2, m2))


def session_date(ts: datetime) -> date:
    """The IST calendar date that owns this instant. Used for the daily alert allowance."""
    return to_utc(ts).astimezone(IST).date()


def in_session(ts: datetime, spec: SessionSpec = SessionSpec()) -> bool:
    ist = to_utc(ts).astimezone(IST)
    return spec.start <= ist.time() < spec.end


def session_bounds(d: date, spec: SessionSpec = SessionSpec()) -> tuple[datetime, datetime]:
    start = datetime.combine(d, spec.start, IST)
    end = datetime.combine(d, spec.end, IST)
    return to_utc(start), to_utc(end)


def is_trading_session_day(d: date, spec: SessionSpec = SessionSpec()) -> bool:
    """A session day exists when the spot market is open for at least part of the window."""
    start, end = session_bounds(d, spec)
    return not market_hours.closed_for_span(start, end, probe_seconds=300)


def seconds_to_session_end(ts: datetime, spec: SessionSpec = SessionSpec()) -> float:
    d = session_date(ts)
    _, end = session_bounds(d, spec)
    return (end - to_utc(ts)).total_seconds()


def next_session_start(ts: datetime, spec: SessionSpec = SessionSpec()) -> datetime:
    d = session_date(ts)
    start, _ = session_bounds(d, spec)
    if to_utc(ts) >= start:
        d = d + timedelta(days=1)
    for _ in range(14):
        if is_trading_session_day(d, spec):
            return session_bounds(d, spec)[0]
        d += timedelta(days=1)
    raise RuntimeError("no trading session day found in the next two weeks; check closures.json")
