"""Dukascopy historical 1-minute candles (spot XAU/USD bank BID/ASK quotes), research only.

URL: https://datafeed.dukascopy.com/datafeed/XAUUSD/YYYY/MM/DD/BID_candles_min_1.bi5 with a
ZERO-BASED month. LZMA-compressed records of 24 bytes: >5If = offset_s, open, close, low,
high (x0.001), volume. Missing minutes are forward-filled with volume 0 (we drop them, and
we drop market-closed minutes). Hard rate limits: one connection, several seconds between files.
"""
from __future__ import annotations

import lzma
import struct
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from .. import market_hours
from ..candles import Candle
from ..timeutil import UTC
from .base import ProviderError

URL = "https://datafeed.dukascopy.com/datafeed/{sym}/{y:04d}/{m0:02d}/{d:02d}/{side}_candles_min_1.bi5"
REC = struct.Struct(">5If")


def decode_bi5(raw: bytes, day: date, *, symbol: str, side: str, scale: float = 0.001) -> list[Candle]:
    if not raw:
        return []
    data = lzma.decompress(raw)
    base = datetime(day.year, day.month, day.day, tzinfo=UTC)
    out = []
    for i in range(0, len(data) - REC.size + 1, REC.size):
        off, o, c, l, h, v = REC.unpack_from(data, i)
        if v <= 0:
            continue   # forward-filled placeholder minute
        ts = base + timedelta(seconds=off)
        if market_hours.is_closed(ts):
            continue
        out.append(Candle(ts, o * scale, h * scale, l * scale, c * scale, float(v), "1m", symbol, f"dukascopy_{side.lower()}", True))
    return out


def download_day(day: date, *, symbol: str = "XAUUSD", side: str = "BID", cache_dir: str | Path = "data/raw/dukascopy",
                 session: requests.Session | None = None, timeout: float = 30) -> bytes:
    cache = Path(cache_dir) / symbol / f"{day.isoformat()}_{side}.bi5"
    if cache.exists():
        return cache.read_bytes()
    http = session or requests.Session()
    url = URL.format(sym=symbol, y=day.year, m0=day.month - 1, d=day.day, side=side)
    r = http.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 xau-signals-research"})
    if r.status_code == 404:
        raw = b""
    elif r.status_code != 200:
        raise ProviderError(f"dukascopy HTTP {r.status_code} for {day}")
    else:
        raw = r.content
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(raw)
    return raw


def download_range(start: date, end: date, *, symbol: str = "XAUUSD", side: str = "BID", pause: float = 4.0,
                   cache_dir: str | Path = "data/raw/dukascopy", log=print) -> list[Candle]:
    http = requests.Session()
    out: list[Candle] = []
    d = start
    while d <= end:
        if d.weekday() == 5:   # Saturday: nothing
            d += timedelta(days=1)
            continue
        cached = (Path(cache_dir) / symbol / f"{d.isoformat()}_{side}.bi5").exists()
        for attempt in range(4):
            try:
                raw = download_day(d, symbol=symbol, side=side, cache_dir=cache_dir, session=http)
                break
            except (ProviderError, requests.RequestException) as e:
                wait = 15 * (attempt + 1)
                log(f"{d}: {e.__class__.__name__} {e}; retry in {wait}s")
                time.sleep(wait)
        else:
            raise ProviderError(f"dukascopy gave up on {d}")
        cs = decode_bi5(raw, d, symbol=symbol, side=side)
        out.extend(cs)
        log(f"{d}: {len(cs)} bars")
        if not cached:
            time.sleep(pause)
        d += timedelta(days=1)
    return out
