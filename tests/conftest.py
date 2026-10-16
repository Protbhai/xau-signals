from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

import pytest

from xau_signals import market_hours
from xau_signals.candles import Candle
from xau_signals.timeutil import IST, interval_seconds

UTC = timezone.utc


@pytest.fixture(autouse=True)
def _closures(tmp_path):
    p = tmp_path / "closures.json"
    p.write_text('{"closed": ["2026-12-25"], "thin": []}', encoding="utf-8")
    market_hours.load_closures(p)
    yield


def ist(y, m, d, hh, mm=0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=IST).astimezone(UTC)


def make_candles(start: datetime, n: int, interval: str, *, price: float = 2650.0, drift: float = 0.0, vol: float = 1.0,
                 seed: int = 1, symbol: str = "XAUUSD", source: str = "test", skip_closed: bool = True) -> list[Candle]:
    """Deterministic synthetic candles. Skips market-closed times so gaps look like the real thing."""
    rnd = random.Random(seed)
    step = timedelta(seconds=interval_seconds(interval))
    out = []
    t = start
    p = price
    while len(out) < n:
        if skip_closed and market_hours.is_closed(t):
            t += step
            continue
        o = p
        c = o + drift + rnd.gauss(0, vol)
        h = max(o, c) + abs(rnd.gauss(0, vol * 0.5))
        l = min(o, c) - abs(rnd.gauss(0, vol * 0.5))
        out.append(Candle(t, o, h, l, c, 100.0, interval, symbol, source, True))
        p = c
        t += step
    return out


def trending_pullback_5m(anchor_open: datetime, *, up: bool = True, symbol: str = "XAUUSD") -> list[Candle]:
    """60 five-minute candles: a steady trend, then a 3-candle pullback to the EMA, then a candle that closes back with the trend.

    The last candle is the setup anchor.
    """
    step = timedelta(minutes=5)
    n = 60
    start = anchor_open - step * (n - 1)
    cs = []
    p = 2650.0
    sgn = 1 if up else -1
    t = start
    for i in range(n):
        if i < n - 4:
            o = p; c = o + sgn * 0.6
            h, l = max(o, c) + 0.3, min(o, c) - 0.3
        elif i < n - 1:                      # pullback toward the mean
            o = p; c = o - sgn * 1.6
            h, l = max(o, c) + 0.2, min(o, c) - 0.2
        else:                                # anchor: touches EMA region then closes with trend
            o = p; c = o + sgn * 1.4
            h, l = (c + 0.3, o - 0.9) if up else (o + 0.9, c - 0.3)
        cs.append(Candle(t, o, h, l, c, 100.0, "5m", symbol, "test", True))
        p = c
        t += step
    return cs


def trending_1h(anchor_open: datetime, *, up: bool = True, n: int = 40, symbol: str = "XAUUSD") -> list[Candle]:
    step = timedelta(hours=1)
    start = anchor_open - step * (n - 1)
    cs = []
    p = 2600.0 if up else 2700.0
    sgn = 1 if up else -1
    t = start
    for _ in range(n):
        o = p; c = o + sgn * 1.5
        cs.append(Candle(t, o, max(o, c) + 0.5, min(o, c) - 0.5, c, 1000.0, "1h", symbol, "test", True))
        p = c
        t += step
    return cs
