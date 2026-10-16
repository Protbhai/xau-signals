"""Binance USDⓈ-M futures klines for XAUUSDT (gold-referenced perpetual).

Verified 16 Oct 2026 (docs/research/data-sources.md): keyless, real time, open-time
stamped, closeTime = open + interval - 1 ms. PRICE TYPE: perpetual futures in USDT,
about $7 above spot at probe time; trades 24/7, so bars at gold-market-closed times
are synthetic and are dropped here via market_hours.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import requests

from .. import market_hours
from ..candles import Candle
from ..timeutil import from_epoch, interval_seconds, now_utc, to_utc
from .base import ProviderError

BASE = "https://fapi.binance.com/fapi/v1/klines"
MAX_LIMIT = 1500


class BinanceProvider:
    name = "binance"
    price_scope = "Binance XAUUSDT perpetual (last trade, USDT; ~$7 over spot) — not spot"

    def __init__(self, session: requests.Session | None = None, timeout: float = 15, throttle_seconds: float = 0.25, base: str = BASE):
        self._http = session or requests.Session()
        self._timeout = timeout
        self._throttle = throttle_seconds
        self._base = base

    def _get(self, params: dict) -> list:
        try:
            r = self._http.get(self._base, params=params, timeout=self._timeout, headers={"User-Agent": "xau-signals/0.1"})
        except requests.RequestException as e:
            raise ProviderError(f"binance request failed: {e.__class__.__name__}") from e
        if r.status_code != 200:
            raise ProviderError(f"binance HTTP {r.status_code}: {r.text[:120]}")
        data = r.json()
        if not isinstance(data, list):
            raise ProviderError(f"binance unexpected body: {str(data)[:120]}")
        return data

    def fetch(self, *, symbol: str, interval: str, start: datetime | None = None, end: datetime | None = None, lookback_bars: int | None = None) -> list[Candle]:
        now = now_utc()
        step_ms = interval_seconds(interval) * 1000
        out: list[Candle] = []
        if start is None and lookback_bars:
            # ask for extra bars to cover weekend/break bars that we will drop
            want = lookback_bars
            params = {"symbol": symbol, "interval": interval, "limit": min(MAX_LIMIT, int(want * 1.6) + 5)}
            if end:
                params["endTime"] = int(to_utc(end).timestamp() * 1000)
            rows = self._get(params)
            out = self._convert(rows, symbol, interval, now)
            return out[-lookback_bars:]
        cur = int(to_utc(start).timestamp() * 1000) if start else None
        end_ms = int(to_utc(end).timestamp() * 1000) if end else int(now.timestamp() * 1000)
        while True:
            params = {"symbol": symbol, "interval": interval, "limit": MAX_LIMIT}
            if cur is not None:
                params["startTime"] = cur
            params["endTime"] = end_ms
            rows = self._get(params)
            if not rows:
                break
            out.extend(self._convert(rows, symbol, interval, now))
            last_open = int(rows[-1][0])
            nxt = last_open + step_ms
            if len(rows) < MAX_LIMIT or nxt >= end_ms:
                break
            cur = nxt
            time.sleep(self._throttle)
        return out

    @staticmethod
    def _convert(rows: list, symbol: str, interval: str, now: datetime) -> list[Candle]:
        out = []
        for r in rows:
            ts = from_epoch(int(r[0]) / 1000)
            close_ms = int(r[6])
            if market_hours.is_closed(ts):
                continue   # synthetic 24/7 bar outside gold hours
            complete = from_epoch((close_ms + 1) / 1000) <= now
            out.append(Candle(ts, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]), interval, symbol, "binance", complete))
        return out
