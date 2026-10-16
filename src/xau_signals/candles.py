"""Candle model, validation and timestamp normalisation.

Rules (from the brief): finite OHLC, consistent symbol, strictly increasing open
times, no duplicate timestamps, no future timestamps, completed-only unless asked,
gaps classified as market closure vs unexplained, freshness measured against now.
Nothing is ever fabricated or interpolated.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import market_hours
from .timeutil import candle_close_time, interval_seconds, now_utc, to_utc


@dataclass(frozen=True)
class Candle:
    ts_open: datetime            # UTC-aware open time
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    interval: str                # e.g. "5m"
    symbol: str
    source: str
    complete: bool = True        # False only when the provider tells us it is still forming

    @property
    def ts_close(self) -> datetime:
        return candle_close_time(self.ts_open, self.interval)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def bullish(self) -> bool:
        return self.close > self.open


@dataclass
class ValidationReport:
    ok: bool
    symbol: str
    interval: str
    n_in: int
    n_out: int
    dropped_forming: int = 0
    dropped_nonfinite: int = 0
    dropped_future: int = 0
    dropped_duplicates: int = 0
    reordered: bool = False
    expected_gaps: list[tuple[datetime, datetime]] = field(default_factory=list)
    unexplained_gaps: list[tuple[datetime, datetime, int]] = field(default_factory=list)  # (from_open, to_open, missing_bars)
    last_close: datetime | None = None
    age_seconds: float | None = None
    fresh: bool | None = None
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"{self.symbol}@{self.interval}: {self.n_out}/{self.n_in} candles"]
        if self.dropped_forming:
            parts.append(f"forming dropped={self.dropped_forming}")
        if self.dropped_nonfinite:
            parts.append(f"nonfinite dropped={self.dropped_nonfinite}")
        if self.dropped_future:
            parts.append(f"future dropped={self.dropped_future}")
        if self.dropped_duplicates:
            parts.append(f"dups dropped={self.dropped_duplicates}")
        if self.unexplained_gaps:
            parts.append(f"UNEXPLAINED gaps={len(self.unexplained_gaps)}")
        if self.age_seconds is not None:
            parts.append(f"age={int(self.age_seconds)}s fresh={self.fresh}")
        if self.errors:
            parts.append("errors=" + "; ".join(self.errors))
        return " ".join(parts)


class CandleValidationError(ValueError):
    pass


def _finite(*xs: float | None) -> bool:
    return all(x is not None and isinstance(x, (int, float)) and math.isfinite(x) for x in xs)


def validate(
    candles: list[Candle],
    *,
    symbol: str,
    interval: str,
    now: datetime | None = None,
    max_age_seconds: float | None = None,
    max_unexplained_gap_bars: int = 1,
    drop_forming: bool = True,
) -> tuple[list[Candle], ValidationReport]:
    """Return (clean candles ascending by ts_open, report).

    Raises CandleValidationError only on a symbol/interval mismatch (wrong instrument),
    because every other defect is something we can drop and report.
    """
    now = to_utc(now or now_utc())
    rep = ValidationReport(ok=True, symbol=symbol, interval=interval, n_in=len(candles), n_out=0)
    step = interval_seconds(interval)

    for c in candles:
        if c.symbol != symbol or c.interval != interval:
            raise CandleValidationError(f"instrument mismatch: got {c.symbol}@{c.interval}, want {symbol}@{interval}")

    out: list[Candle] = []
    for c in candles:
        if not _finite(c.open, c.high, c.low, c.close) or c.low > c.high or c.low <= 0:
            rep.dropped_nonfinite += 1
            continue
        if not (c.low - 1e-9 <= c.open <= c.high + 1e-9 and c.low - 1e-9 <= c.close <= c.high + 1e-9):
            rep.dropped_nonfinite += 1
            continue
        ts = to_utc(c.ts_open)
        if ts > now:
            rep.dropped_future += 1
            continue
        # A candle whose close time has not yet arrived is still forming regardless of the flag.
        forming = (not c.complete) or (candle_close_time(ts, interval) > now)
        if forming and drop_forming:
            rep.dropped_forming += 1
            continue
        out.append(c if ts == c.ts_open else Candle(ts, c.open, c.high, c.low, c.close, c.volume, c.interval, c.symbol, c.source, c.complete))

    # ordering + duplicates
    sorted_out = sorted(out, key=lambda c: c.ts_open)
    rep.reordered = sorted_out != out
    dedup: list[Candle] = []
    for c in sorted_out:
        if dedup and dedup[-1].ts_open == c.ts_open:
            rep.dropped_duplicates += 1
            if dedup[-1] != c:
                rep.errors.append(f"conflicting duplicate at {c.ts_open.isoformat()}")
            continue
        dedup.append(c)
    out = dedup

    # gaps: expected if the market is closed for the whole missing span, else unexplained
    for a, b in zip(out, out[1:]):
        missing = int((b.ts_open - a.ts_open).total_seconds() // step) - 1
        if missing <= 0:
            continue
        span_start = a.ts_open + timedelta(seconds=step)
        span_end = b.ts_open
        if market_hours.closed_for_span(span_start, span_end):
            rep.expected_gaps.append((span_start, span_end))
        elif missing > max_unexplained_gap_bars:
            rep.unexplained_gaps.append((a.ts_open, b.ts_open, missing))
        else:
            rep.expected_gaps.append((span_start, span_end))  # within tolerance; recorded, not alarming

    rep.n_out = len(out)
    if out:
        rep.last_close = out[-1].ts_close
        rep.age_seconds = (now - rep.last_close).total_seconds()
        if max_age_seconds is not None:
            # If the market is closed right now, the last candle can legitimately be old.
            rep.fresh = rep.age_seconds <= max_age_seconds or market_hours.is_closed(now)
    else:
        rep.errors.append("no completed candles")
    rep.ok = not rep.errors and not rep.unexplained_gaps
    return out, rep
