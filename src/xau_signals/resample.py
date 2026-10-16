"""Aggregate 1m candles into higher intervals without inventing bars.

A target bar exists only if at least one source bar falls in it; its OHLC come
from the source bars present. Partial bars (fewer than expected source bars) are
kept but reported, so a backtest can decide what to do with them.
"""
from __future__ import annotations

from collections import OrderedDict

from .candles import Candle
from .timeutil import floor_to_interval, interval_seconds


def resample(candles: list[Candle], interval: str) -> tuple[list[Candle], int]:
    """Return (bars, n_partial). Input must be a single lower interval, any order."""
    if not candles:
        return [], 0
    src_step = interval_seconds(candles[0].interval)
    dst_step = interval_seconds(interval)
    if dst_step % src_step:
        raise ValueError(f"{interval} is not a multiple of {candles[0].interval}")
    expected = dst_step // src_step
    buckets: "OrderedDict" = OrderedDict()
    for c in sorted(candles, key=lambda c: c.ts_open):
        k = floor_to_interval(c.ts_open, interval)
        buckets.setdefault(k, []).append(c)
    out, partial = [], 0
    for k, cs in buckets.items():
        if len(cs) < expected:
            partial += 1
        vol = None if any(c.volume is None for c in cs) else sum(c.volume for c in cs)
        out.append(Candle(k, cs[0].open, max(c.high for c in cs), min(c.low for c in cs), cs[-1].close, vol, interval, cs[0].symbol, cs[0].source, True))
    return out, partial
